"""Liquidação idempotente de lotes vencidos."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from functools import partial
from typing import TYPE_CHECKING
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from auctions.events import publish_lot_event, publish_user_event
from auctions.models import Bid, Lot, Receipt
from auctions.services.audit import write_anchor
from auctions.services.integrity import bid_hashes, bid_payload
from users.models import User
from wallet.models import Wallet, WalletTransaction
from wallet.services import settle_credit, settle_debit

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal
    from uuid import UUID

logger = logging.getLogger(__name__)


def _bid_hashes(bid: Bid) -> tuple[str, str]:
    return bid_hashes(bid_payload(bid))


def _chain_error(lot: Lot, bids: list[Bid]) -> str:
    if len(bids) != lot.bids_count:
        return "Contagem de lances divergente."
    previous = "0" * 64
    for expected, bid in enumerate(bids, start=1):
        content_hash, chain_hash = _bid_hashes(bid)
        if bid.sequence != expected or bid.prev_hash != previous:
            return "Sequência ou elo anterior inválido."
        if bid.content_hash != content_hash or bid.hash != chain_hash:
            return "Hash do histórico inválido."
        previous = bid.hash
    if (bids[-1].hash if bids else "") != lot.history_head:
        return "Cabeça do histórico divergente."
    return ""


def _finance_error(
    lot: Lot, bids: list[Bid], wallets: dict[UUID, Wallet]
) -> str:
    if not bids:
        return ""
    last = bids[-1]
    if (
        last.bidder_id != lot.current_winner_id
        or last.amount != lot.current_bid
    ):
        return "Líder ou valor atual divergente do último lance."
    winning_wallet = wallets.get(last.bidder_id)
    if winning_wallet is None:
        return "Carteira do vencedor ausente."
    if lot.seller_id not in wallets:
        return "Carteira do leiloeiro ausente."
    return _hold_error(last, winning_wallet)


def _hold_error(last: Bid, winning_wallet: Wallet) -> str:
    if winning_wallet.committed < last.amount:
        return "Reserva financeira do vencedor insuficiente."
    hold = (
        WalletTransaction.objects.filter(
            wallet=winning_wallet,
            type=WalletTransaction.Type.BID_HOLD,
            reference_kind=WalletTransaction.ReferenceKind.BID,
            reference_id=last.pk,
        )
        .order_by("-created_at")
        .first()
    )
    if hold is None or hold.amount != last.amount:
        return "Reserva financeira do último lance ausente ou divergente."
    release = WalletTransaction.objects.filter(
        wallet=winning_wallet,
        type__in=(
            WalletTransaction.Type.BID_RELEASE,
            WalletTransaction.Type.SETTLEMENT_DEBIT,
        ),
        reference_id=last.pk,
        created_at__gt=hold.created_at,
    ).exists()
    if release:
        return (
            "Reserva financeira do último lance já foi liberada ou debitada."
        )
    return ""


def _integrity_error(lot: Lot, wallets: dict[UUID, Wallet]) -> str:
    bids = list(Bid.objects.filter(lot=lot).order_by("sequence"))
    return _chain_error(lot, bids) or _finance_error(lot, bids, wallets)


def _receipt_payload(
    lot: Lot,
    winner: User,
    final_price: Decimal,
    issued_at: datetime,
    token: UUID,
) -> dict[str, str | int]:
    return {
        "token": str(token),
        "lot_id": str(lot.pk),
        "lot_code": lot.code,
        "winner_alias": winner.public_alias,
        "seller_alias": lot.seller.public_alias,
        "item_source": lot.source,
        "item_external_id": lot.external_id,
        "item_title": lot.title,
        "item_image_url": lot.image_url,
        "final_price": f"{final_price:.2f}",
        "issued_at": issued_at.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "audit_head": lot.history_head,
        "bid_count": lot.bids_count,
        "hash_version": 1,
    }


def _record_settlement_error(lot: Lot, now: datetime, detail: str) -> None:
    lot.settlement_checked_at = now
    lot.settlement_error = detail
    lot.state_version += 1
    lot.save(
        update_fields=(
            "settlement_checked_at",
            "settlement_error",
            "state_version",
            "updated_at",
        )
    )
    logger.error("Liquidação bloqueada para lote %s: %s", lot.code, detail)


def _close_empty_lot(lot: Lot, now: datetime) -> None:
    lot.settlement_checked_at = now
    lot.settled_at = now
    lot.state_version += 1
    lot.save(
        update_fields=(
            "settlement_checked_at",
            "settled_at",
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
    transaction.on_commit(
        partial(
            publish_lot_event,
            lot.pk,
            "lot.closed",
            lot.state_version,
            {"winner_alias": None, "final_price": None, "receipt_token": None},
        )
    )


def _create_receipt(
    lot: Lot, winner: User, final_price: Decimal, now: datetime
) -> Receipt:
    token = uuid4()
    receipt_payload = _receipt_payload(lot, winner, final_price, now, token)
    canonical = json.dumps(
        receipt_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    verification_hash = hmac.new(
        settings.RECEIPT_SECRET.encode(), canonical.encode(), hashlib.sha256
    ).hexdigest()
    return Receipt.objects.create(
        token=token,
        code=f"R-{lot.pk.hex[:12].upper()}",
        lot=lot,
        winner=winner,
        winner_alias=winner.public_alias,
        seller_alias=lot.seller.public_alias,
        lot_code=lot.code,
        item_source=lot.source,
        item_external_id=lot.external_id,
        item_title=lot.title,
        item_image_url=lot.image_url,
        final_price=final_price,
        issued_at=now,
        audit_head=lot.history_head,
        bid_count=lot.bids_count,
        verification_hash=verification_hash,
    )


def _complete_sale(
    lot: Lot, wallets: dict[UUID, Wallet], now: datetime
) -> Receipt | None:
    winner_id = lot.current_winner_id
    final_price = lot.current_bid
    if winner_id is None or final_price is None:
        _record_settlement_error(lot, now, "Líder ou preço final ausente.")
        return None
    winner_wallet = wallets[winner_id]
    seller_wallet = wallets[lot.seller_id]
    last_bid = Bid.objects.get(lot=lot, sequence=lot.bids_count)
    settle_debit(winner_wallet, final_price, lot.pk, last_bid.pk)
    settle_credit(seller_wallet, final_price, lot.pk)
    winner = User.objects.get(pk=winner_id)
    receipt = _create_receipt(lot, winner, final_price, now)
    lot.winner_id = winner_id
    lot.final_price = final_price
    lot.settlement_checked_at = now
    lot.settled_at = now
    lot.state_version += 1
    lot.save(
        update_fields=(
            "settlement_checked_at",
            "winner",
            "final_price",
            "settled_at",
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
    transaction.on_commit(
        partial(
            publish_lot_event,
            lot.pk,
            "lot.closed",
            lot.state_version,
            {
                "winner_alias": winner.public_alias,
                "final_price": f"{final_price:.2f}",
                "receipt_token": str(receipt.token),
            },
        )
    )
    transaction.on_commit(
        partial(
            publish_user_event,
            winner_id,
            "user.won",
            {
                "lot_id": str(lot.pk),
                "lot_code": lot.code,
                "receipt_token": str(receipt.token),
                "state_version": lot.state_version,
            },
        )
    )
    transaction.on_commit(
        partial(
            publish_user_event,
            lot.seller_id,
            "user.sold",
            {
                "lot_id": str(lot.pk),
                "lot_code": lot.code,
                "final_price": f"{final_price:.2f}",
                "state_version": lot.state_version,
            },
        )
    )
    return receipt


@transaction.atomic
def settle_lot(lot_id: UUID) -> Receipt | None:
    """Liquida lote vencido ou grava a inconsistência sem cobrar."""
    lot = Lot.objects.select_for_update().filter(pk=lot_id).first()
    if (
        lot is None
        or lot.cancelled_at is not None
        or lot.settled_at is not None
        or lot.settlement_error
    ):
        return None
    user_ids = {lot.seller_id}
    if lot.current_winner_id is not None:
        user_ids.add(lot.current_winner_id)
    wallets = {
        wallet.user_id: wallet
        for wallet in Wallet.objects.select_for_update()
        .filter(user_id__in=user_ids)
        .order_by("pk")
    }
    now = timezone.now()
    if lot.ends_at > now:
        return None
    problem = _integrity_error(lot, wallets)
    if problem:
        _record_settlement_error(lot, now, problem)
        return None
    if lot.bids_count == 0:
        _close_empty_lot(lot, now)
        return None
    return _complete_sale(lot, wallets, now)


def settle_if_due(lot: Lot) -> Receipt | None:
    """Liquida sob demanda quando o prazo do lote já passou."""
    if (
        lot.cancelled_at is not None
        or lot.settled_at is not None
        or lot.settlement_error
        or lot.ends_at > timezone.now()
    ):
        return None
    return settle_lot(lot.pk)


def settle_due_lots(*, batch_size: int = 50) -> int:
    """Processa em lotes limitados, cada lote em sua própria transação."""
    due_ids = tuple(
        Lot.objects.filter(
            settled_at__isnull=True,
            cancelled_at__isnull=True,
            settlement_error="",
            ends_at__lte=timezone.now(),
        )
        .order_by("ends_at")
        .values_list("pk", flat=True)[:batch_size]
    )
    processed = 0
    for lot_id in due_ids:
        try:
            settle_lot(lot_id)
        except Exception:
            logger.exception("Falha isolada ao liquidar lote %s", lot_id)
        else:
            processed += 1
    return processed
