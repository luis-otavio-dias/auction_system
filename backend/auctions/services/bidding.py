"""Serviços transacionais de lances."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, timedelta
from functools import partial
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from auctions.events import (
    EventValue,
    publish_lot_event,
    publish_user_event,
)
from auctions.models import Bid, Lot
from auctions.services.audit import write_anchor
from auctions.services.integrity import GENESIS_HASH, BidPayload, bid_hashes
from wallet.models import Wallet
from wallet.services import hold, release

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal
    from uuid import UUID

    from users.models import User


@dataclass(frozen=True)
class BidPlacement:
    """Lance aceito e metadado de replay idempotente."""

    bid: Bid
    replayed: bool


class BidError(Exception):
    """Erro de regra de lance com código e HTTP associados."""

    code = "BID_ERROR"
    detail = "Não foi possível aceitar o lance."
    status_code = 409

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)


class BidNotFoundError(BidError):
    code = "LOT_NOT_FOUND"
    detail = "Lote não encontrado."
    status_code = 404


class BidValidationError(BidError):
    code = "BID_AMOUNT_MISMATCH"
    detail = "O valor deve corresponder ao próximo lance mínimo."
    status_code = 422


class BidBelowMinimumError(BidError):
    code = "BID_BELOW_MINIMUM"
    detail = "O valor está abaixo do lance mínimo atual."
    status_code = 422


class BidRoleError(BidError):
    code = "FORBIDDEN_ROLE"
    detail = "Apenas licitantes podem participar."
    status_code = 403


class SellerBidError(BidError):
    code = "SELLER_CANNOT_BID"
    detail = "O leiloeiro não pode dar lance no próprio lote."
    status_code = 403


class LotCancelledBidError(BidError):
    code = "LOT_CANCELLED"
    detail = "O lote está cancelado."


class LotSettledBidError(BidError):
    code = "LOT_SETTLED"
    detail = "O lote já foi liquidado."


class LotNotStartedBidError(BidError):
    code = "LOT_NOT_STARTED"
    detail = "O lote ainda não começou."


class LotEndedBidError(BidError):
    code = "LOT_ENDED"
    detail = "O lote já foi encerrado."


class AlreadyLeadingBidError(BidError):
    code = "ALREADY_LEADING"
    detail = "Você já está liderando este lote."


class InsufficientFundsBidError(BidError):
    code = "INSUFFICIENT_FUNDS"
    detail = "Saldo disponível insuficiente."

    def __init__(self, available: Decimal, minimum_bid: Decimal) -> None:
        self.available = available
        self.minimum_bid = minimum_bid
        super().__init__()


class IdempotencyKeyReusedError(BidError):
    code = "IDEMPOTENCY_KEY_REUSED"
    detail = "A chave de idempotência já foi usada com outro valor."


def _validate_bid(
    *, lot: Lot, bidder: User, amount: Decimal, wallet: Wallet, now: datetime
) -> None:
    _validate_bidder_access(lot, bidder)
    _validate_lot_window(lot, bidder, now)
    if amount < lot.minimum_bid:
        raise BidBelowMinimumError
    if amount != lot.minimum_bid:
        raise BidValidationError
    if wallet.available < amount:
        raise InsufficientFundsBidError(wallet.available, amount)


def _validate_bidder_access(lot: Lot, bidder: User) -> None:
    if not bidder.is_bidder:
        raise BidRoleError
    if lot.seller_id == bidder.pk:
        raise SellerBidError


def _validate_lot_window(lot: Lot, bidder: User, now: datetime) -> None:
    if lot.cancelled_at is not None:
        raise LotCancelledBidError
    if lot.settled_at is not None:
        raise LotSettledBidError
    if now < lot.starts_at:
        raise LotNotStartedBidError
    if now >= lot.ends_at:
        raise LotEndedBidError
    if lot.current_winner_id == bidder.pk:
        raise AlreadyLeadingBidError


def _locked_wallets(lot: Lot, bidder: User) -> dict[UUID, Wallet]:
    user_ids = {bidder.pk}
    if lot.current_winner_id is not None:
        user_ids.add(lot.current_winner_id)
    return {
        wallet.user_id: wallet
        for wallet in Wallet.objects.select_for_update()
        .filter(user_id__in=user_ids)
        .order_by("pk")
    }


def _idempotent_bid(
    *, lot: Lot, bidder: User, amount: Decimal, client_bid_id: UUID | None
) -> Bid | None:
    if client_bid_id is None:
        return None
    prior = Bid.objects.filter(
        lot=lot, bidder=bidder, client_bid_id=client_bid_id
    ).first()
    if prior is None:
        return None
    if prior.amount != amount:
        raise IdempotencyKeyReusedError
    return prior


def _release_previous_leader(*, lot: Lot, wallets: dict[UUID, Wallet]) -> None:
    if lot.current_winner_id is None or lot.current_bid is None:
        return
    prior_bid = Bid.objects.get(lot=lot, sequence=lot.bids_count)
    release(
        wallets[lot.current_winner_id].pk,
        lot.current_bid,
        reference_id=prior_bid.pk,
        idempotency_key=f"bid-release:{prior_bid.pk}",
    )


def _make_bid(
    *,
    lot: Lot,
    bidder: User,
    amount: Decimal,
    now: datetime,
    client_bid_id: UUID | None,
) -> Bid:
    sequence = lot.bids_count + 1
    before = lot.ends_at
    after = max(before, now + timedelta(minutes=2))
    previous = lot.history_head or GENESIS_HASH
    payload: BidPayload = {
        "lot_id": str(lot.pk),
        "sequence": sequence,
        "bidder_id": str(bidder.pk),
        "bidder_alias": bidder.public_alias,
        "amount": f"{amount:.2f}",
        "placed_at": now.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "ends_at_before": before.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "ends_at_after": after.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "prev_hash": previous,
        "hash_version": 1,
    }
    content_hash, chain_hash = bid_hashes(payload)
    bid = Bid.objects.create(
        lot=lot,
        bidder=bidder,
        bidder_alias=bidder.public_alias,
        sequence=sequence,
        amount=amount,
        placed_at=now,
        prev_hash=previous,
        content_hash=content_hash,
        hash=chain_hash,
        ends_at_before=before,
        ends_at_after=after,
        client_bid_id=client_bid_id,
    )
    _update_lot_after_bid(lot=lot, bidder=bidder, bid=bid, after=after)
    return bid


def _update_lot_after_bid(
    *, lot: Lot, bidder: User, bid: Bid, after: datetime
) -> None:
    wallet = Wallet.objects.get(user=bidder)
    hold(
        wallet.pk,
        bid.amount,
        reference_id=bid.pk,
        idempotency_key=f"bid-hold:{bid.pk}",
    )
    lot.current_bid = bid.amount
    lot.current_winner = bidder
    lot.bids_count = bid.sequence
    lot.history_head = bid.hash
    lot.ends_at = after
    if after > bid.ends_at_before:
        lot.extension_count += 1
    lot.state_version += 1
    lot.save(
        update_fields=(
            "current_bid",
            "current_winner",
            "bids_count",
            "history_head",
            "ends_at",
            "extension_count",
            "state_version",
            "updated_at",
        )
    )
    transaction.on_commit(
        partial(
            write_anchor,
            lot.pk,
            lot.bids_count,
            lot.history_head,
            lot.bids_count,
        )
    )


@transaction.atomic
def place_bid_result(
    *,
    lot_id: UUID,
    bidder: User,
    amount: Decimal,
    client_bid_id: UUID | None = None,
) -> BidPlacement:
    """Aceita lance, move as reservas e avança a cadeia de integridade."""
    lot = Lot.objects.select_for_update().filter(pk=lot_id).first()
    if lot is None:
        raise BidNotFoundError
    prior = _idempotent_bid(
        lot=lot, bidder=bidder, amount=amount, client_bid_id=client_bid_id
    )
    if prior is not None:
        return BidPlacement(prior, replayed=True)
    wallets = _locked_wallets(lot, bidder)
    now = timezone.now()
    _validate_bid(
        lot=lot,
        bidder=bidder,
        amount=amount,
        wallet=wallets[bidder.pk],
        now=now,
    )
    previous_leader_id = lot.current_winner_id
    _release_previous_leader(lot=lot, wallets=wallets)
    bid = _make_bid(
        lot=lot,
        bidder=bidder,
        amount=amount,
        now=now,
        client_bid_id=client_bid_id,
    )
    payload: dict[str, EventValue] = {
        "amount": f"{bid.amount:.2f}",
        "bidder_alias": bid.bidder_alias,
        "sequence": bid.sequence,
        "ends_at": bid.ends_at_after.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "bids_count": lot.bids_count,
        "server_time": now.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }
    transaction.on_commit(
        partial(
            publish_lot_event,
            lot.pk,
            "bid.accepted",
            lot.state_version,
            payload,
        )
    )
    if bid.ends_at_after > bid.ends_at_before:
        transaction.on_commit(
            partial(
                publish_lot_event,
                lot.pk,
                "lot.extended",
                lot.state_version,
                {
                    "ends_at": bid.ends_at_after.astimezone(UTC)
                    .isoformat(timespec="microseconds")
                    .replace("+00:00", "Z"),
                    "server_time": now.astimezone(UTC)
                    .isoformat(timespec="microseconds")
                    .replace("+00:00", "Z"),
                },
            )
        )
    if previous_leader_id is not None:
        transaction.on_commit(
            partial(
                publish_user_event,
                previous_leader_id,
                "user.outbid",
                {
                    "lot_id": str(lot.pk),
                    "lot_code": lot.code,
                    "state_version": lot.state_version,
                },
            )
        )
    return BidPlacement(bid, replayed=False)


def place_bid(
    *,
    lot_id: UUID,
    bidder: User,
    amount: Decimal,
    client_bid_id: UUID | None = None,
) -> Bid:
    """Aceita lance e devolve a entidade criada ou reproduzida."""
    return place_bid_result(
        lot_id=lot_id,
        bidder=bidder,
        amount=amount,
        client_bid_id=client_bid_id,
    ).bid
