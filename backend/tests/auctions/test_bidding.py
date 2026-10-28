"""Testes das regras de lance e extensão do prazo."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from typing import Literal
from uuid import UUID, uuid4

import pytest
from django.db import (
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.utils import timezone

from auctions.models import Lot
from auctions.services.bidding import (
    BidError,
    InsufficientFundsBidError,
    place_bid,
)
from auctions.services.lots import create_lot
from users.models import User
from wallet.models import Wallet, WalletTransaction

pytestmark = pytest.mark.django_db


def test_bid_holds_funds_and_updates_lot(lot, bidder) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))

    bid = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))

    wallet.refresh_from_db()
    lot.refresh_from_db()
    assert bid.sequence == 1
    assert wallet.committed == Decimal("1000.00")
    assert lot.current_winner_id == bidder.pk
    assert lot.current_bid == Decimal("1000.00")
    assert lot.bids_count == 1
    assert (
        WalletTransaction.objects.filter(
            wallet=wallet, type=WalletTransaction.Type.BID_HOLD
        ).count()
        == 1
    )


@pytest.mark.parametrize(
    ("amount", "expected_code"),
    [
        (Decimal("999.00"), "BID_BELOW_MINIMUM"),
        (Decimal("1001.00"), "BID_AMOUNT_MISMATCH"),
    ],
)
def test_bid_amount_error_codes(
    lot, bidder, amount: Decimal, expected_code: str
) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))

    with pytest.raises(BidError) as error:
        place_bid(lot_id=lot.pk, bidder=bidder, amount=amount)

    assert error.value.code == expected_code


@pytest.mark.parametrize(
    ("state", "expected_code"),
    [
        ("not_started", "LOT_NOT_STARTED"),
        ("ended", "LOT_ENDED"),
        ("cancelled", "LOT_CANCELLED"),
        ("settled", "LOT_SETTLED"),
    ],
)
def test_bid_rejects_lot_state(
    lot, bidder, state: str, expected_code: str
) -> None:
    now = timezone.now()
    if state == "not_started":
        lot.starts_at = now + timedelta(minutes=1)
    elif state == "ended":
        lot.ends_at = now - timedelta(seconds=1)
    elif state == "cancelled":
        lot.cancelled_at = now
    else:
        lot.settled_at = now
    lot.save(
        update_fields=("starts_at", "ends_at", "cancelled_at", "settled_at")
    )

    with pytest.raises(BidError) as error:
        place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))

    assert error.value.code == expected_code


def test_bid_rejects_role_and_own_lot(lot, seller) -> None:
    with pytest.raises(BidError) as forbidden:
        place_bid(lot_id=lot.pk, bidder=seller, amount=Decimal("1000.00"))
    assert forbidden.value.code == "FORBIDDEN_ROLE"

    seller.role = User.Role.BIDDER
    seller.save(update_fields=("role",))
    with pytest.raises(BidError) as own_lot:
        place_bid(lot_id=lot.pk, bidder=seller, amount=Decimal("1000.00"))
    assert own_lot.value.code == "SELLER_CANNOT_BID"


def test_bid_rejects_leader_and_insufficient_funds(lot, bidder) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("1000.00")
    wallet.save(update_fields=("balance",))
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    with pytest.raises(BidError) as leader:
        place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1100.00"))
    assert leader.value.code == "ALREADY_LEADING"

    other = User.objects.create_user(
        email="no-funds@example.com", password="pass-123456", role="BIDDER"
    )
    with pytest.raises(BidError) as insufficient:
        place_bid(lot_id=lot.pk, bidder=other, amount=Decimal("1100.00"))
    assert insufficient.value.code == "INSUFFICIENT_FUNDS"
    assert isinstance(insufficient.value, InsufficientFundsBidError)
    assert insufficient.value.available == Decimal("0.00")
    assert insufficient.value.minimum_bid == Decimal("1100.00")


def test_bid_idempotency_returns_existing_and_conflict_rejects(
    lot, bidder
) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))
    client_bid_id = uuid4()
    original = place_bid(
        lot_id=lot.pk,
        bidder=bidder,
        amount=Decimal("1000.00"),
        client_bid_id=client_bid_id,
    )

    replay = place_bid(
        lot_id=lot.pk,
        bidder=bidder,
        amount=Decimal("1000.00"),
        client_bid_id=client_bid_id,
    )
    assert replay.pk == original.pk
    with pytest.raises(BidError) as conflict:
        place_bid(
            lot_id=lot.pk,
            bidder=bidder,
            amount=Decimal("1100.00"),
            client_bid_id=client_bid_id,
        )
    assert conflict.value.code == "IDEMPOTENCY_KEY_REUSED"
    assert (
        WalletTransaction.objects.filter(
            wallet=wallet,
            type=WalletTransaction.Type.BID_HOLD,
        ).count()
        == 1
    )
    assert (
        WalletTransaction.objects.filter(
            wallet=wallet,
            type=WalletTransaction.Type.BID_RELEASE,
        ).count()
        == 0
    )
    lot.refresh_from_db()
    assert lot.bids_count == 1


def test_bid_replays_original_after_lot_has_ended(lot, bidder) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))
    client_bid_id = uuid4()
    original = place_bid(
        lot_id=lot.pk,
        bidder=bidder,
        amount=Decimal("1000.00"),
        client_bid_id=client_bid_id,
    )
    lot.ends_at = timezone.now() - timedelta(seconds=1)
    lot.save(update_fields=("ends_at",))

    replay = place_bid(
        lot_id=lot.pk,
        bidder=bidder,
        amount=Decimal("1000.00"),
        client_bid_id=client_bid_id,
    )

    assert replay.pk == original.pk


@pytest.mark.parametrize(
    ("seconds_before", "should_extend"),
    [(121, False), (120, False), (119, True)],
)
def test_anti_sniping_boundaries(
    lot,
    bidder,
    monkeypatch: pytest.MonkeyPatch,
    seconds_before: int,
    should_extend: Literal[False, True],
) -> None:
    fixed_now = timezone.now()
    lot.starts_at = fixed_now - timedelta(hours=1)
    lot.ends_at = fixed_now + timedelta(seconds=seconds_before)
    lot.original_ends_at = lot.ends_at
    lot.save(update_fields=("starts_at", "ends_at", "original_ends_at"))
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))
    monkeypatch.setattr(
        "auctions.services.bidding.timezone.now", lambda: fixed_now
    )

    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))

    lot.refresh_from_db()
    assert lot.ends_at == (
        fixed_now + timedelta(minutes=2)
        if should_extend
        else fixed_now + timedelta(seconds=seconds_before)
    )
    assert lot.extension_count == int(should_extend)


@pytest.mark.django_db(transaction=True)
def test_concurrent_bids_are_serialized_by_lot_lock(lot, bidder) -> None:
    assert connection.vendor == "postgresql"
    other = User.objects.create_user(
        email="second-bidder@example.com",
        password="pass-123456",
        role="BIDDER",
    )
    for user in (bidder, other):
        wallet = Wallet.objects.get(user=user)
        wallet.balance = Decimal("10000.00")
        wallet.save(update_fields=("balance",))
    barrier = Barrier(2)

    def submit(user_id: str) -> bool:
        close_old_connections()
        barrier.wait()
        try:
            place_bid(
                lot_id=lot.pk,
                bidder=User.objects.get(pk=user_id),
                amount=Decimal("1000.00"),
            )
        except BidError:
            return False
        else:
            return True
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(submit, (str(bidder.pk), str(other.pk))))

    lot.refresh_from_db()
    assert sum(outcomes) == 1
    assert lot.bids_count == 1
    assert lot.current_bid == Decimal("1000.00")
    assert connection.vendor == "postgresql"


@pytest.mark.django_db(transaction=True)
def test_same_wallet_cannot_hold_funds_in_two_lots_concurrently(
    lot, seller, bidder, other_catalog_item
) -> None:
    assert connection.vendor == "postgresql"
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("1000.00")
    wallet.save(update_fields=("balance",))
    now = timezone.now()
    second_lot = create_lot(
        seller=seller,
        catalog_item=other_catalog_item,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        starting_bid=Decimal("1000.00"),
        min_increment=Decimal("100.00"),
        cache_image=False,
    )
    barrier = Barrier(2)

    def submit(lot_id: UUID) -> bool:
        close_old_connections()
        barrier.wait()
        try:
            place_bid(
                lot_id=lot_id,
                bidder=User.objects.get(pk=bidder.pk),
                amount=Decimal("1000.00"),
            )
        except BidError:
            return False
        finally:
            connections.close_all()
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(submit, (lot.pk, second_lot.pk)))

    wallet.refresh_from_db()
    assert sum(outcomes) == 1
    assert wallet.committed == Decimal("1000.00")
    assert wallet.available == Decimal("0.00")


@pytest.mark.django_db(transaction=True)
def test_bid_waiting_for_lot_lock_observes_committed_expiration(
    lot, bidder
) -> None:
    assert connection.vendor == "postgresql"
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))
    barrier = Barrier(2)

    def submit() -> str | None:
        close_old_connections()
        barrier.wait()
        try:
            place_bid(
                lot_id=lot.pk,
                bidder=User.objects.get(pk=bidder.pk),
                amount=Decimal("1000.00"),
            )
        except BidError as exc:
            return exc.code
        finally:
            connections.close_all()
        return None

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(submit)
        with transaction.atomic():
            Lot.objects.select_for_update().get(pk=lot.pk)
            barrier.wait()
            Lot.objects.filter(pk=lot.pk).update(
                ends_at=timezone.now() - timedelta(seconds=1)
            )
        assert future.result(timeout=10) == "LOT_ENDED"
