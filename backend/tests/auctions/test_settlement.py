"""Testes de liquidação e de integridade financeira."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from django.db import close_old_connections, connection, connections
from django.utils import timezone

from auctions.models import Bid, Lot, Receipt
from auctions.services.bidding import place_bid
from auctions.services.lots import create_lot
from auctions.services.settlement import settle_due_lots, settle_lot
from users.models import User
from wallet.models import Wallet, WalletTransaction

pytestmark = pytest.mark.django_db


def fund(user: User, amount: str = "10000.00") -> Wallet:
    wallet = Wallet.objects.get(user=user)
    wallet.balance = Decimal(amount)
    wallet.save(update_fields=("balance",))
    return wallet


def test_settlement_debits_winner_credits_seller_and_issues_receipt(
    lot, bidder, seller
) -> None:
    other = User.objects.create_user(
        email="another@example.com", password="pass-123456", role="BIDDER"
    )
    winner_wallet = fund(bidder)
    fund(other)
    seller_wallet = Wallet.objects.get(user=seller)
    first = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    place_bid(lot_id=lot.pk, bidder=other, amount=Decimal("1100.00"))
    lot.ends_at = timezone.now() - timedelta(seconds=1)
    lot.save(update_fields=("ends_at",))

    receipt = settle_lot(lot.pk)

    assert receipt is not None
    lot.refresh_from_db()
    winner_wallet.refresh_from_db()
    seller_wallet.refresh_from_db()
    other_wallet = Wallet.objects.get(user=other)
    assert lot.winner_id == other.pk
    assert lot.final_price == Decimal("1100.00")
    assert lot.settled_at is not None
    assert other_wallet.balance == Decimal("8900.00")
    assert winner_wallet.balance == Decimal("10000.00")
    assert winner_wallet.committed == Decimal("0.00")
    assert seller_wallet.balance == Decimal("1100.00")
    assert Receipt.objects.filter(lot=lot).count() == 1
    assert WalletTransaction.objects.filter(
        reference_id=first.pk, type=WalletTransaction.Type.BID_RELEASE
    ).exists()


def test_settle_empty_lot_without_receipt(lot) -> None:
    lot.ends_at = timezone.now() - timedelta(seconds=1)
    lot.save(update_fields=("ends_at",))

    assert settle_lot(lot.pk) is None

    lot.refresh_from_db()
    assert lot.settled_at is not None
    assert lot.winner_id is None
    assert not Receipt.objects.filter(lot=lot).exists()


def test_corrupt_history_blocks_charging(lot, bidder, seller) -> None:
    wallet = fund(bidder)
    fund(seller)
    bid = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    Bid.objects.filter(pk=bid.pk).update(amount=Decimal("1001.00"))
    lot.ends_at = timezone.now() - timedelta(seconds=1)
    lot.save(update_fields=("ends_at",))

    assert settle_lot(lot.pk) is None

    lot.refresh_from_db()
    wallet.refresh_from_db()
    assert lot.settlement_error
    assert lot.settled_at is None
    assert wallet.balance == Decimal("10000.00")
    assert not Receipt.objects.filter(lot=lot).exists()


def test_missing_winning_hold_blocks_charging(lot, bidder, seller) -> None:
    wallet = fund(bidder)
    fund(seller)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    wallet.refresh_from_db()
    wallet.committed = Decimal("0.00")
    wallet.save(update_fields=("committed",))
    lot.ends_at = timezone.now() - timedelta(seconds=1)
    lot.save(update_fields=("ends_at",))

    assert settle_lot(lot.pk) is None

    lot.refresh_from_db()
    wallet.refresh_from_db()
    assert lot.settlement_error
    assert lot.settlement_checked_at is not None
    assert lot.settled_at is None
    assert wallet.balance == Decimal("10000.00")
    assert not Receipt.objects.filter(lot=lot).exists()


def test_cancelled_lot_is_not_settled(lot, seller) -> None:
    lot.cancelled_at = timezone.now()
    lot.cancelled_by = seller
    lot.ends_at = timezone.now() - timedelta(seconds=1)
    lot.save(update_fields=("cancelled_at", "cancelled_by", "ends_at"))

    assert settle_lot(lot.pk) is None
    lot.refresh_from_db()
    assert lot.settled_at is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_settlement_creates_one_receipt(lot, bidder) -> None:
    assert connection.vendor == "postgresql"
    fund(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    Lot.objects.filter(pk=lot.pk).update(
        ends_at=timezone.now() - timedelta(seconds=1)
    )
    barrier = Barrier(2)

    def settle() -> str | None:
        close_old_connections()
        barrier.wait()
        try:
            receipt = settle_lot(lot.pk)
            return str(receipt.pk) if receipt is not None else None
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (executor.submit(settle), executor.submit(settle))
        outcomes = tuple(future.result() for future in futures)

    assert sum(outcome is not None for outcome in outcomes) == 1
    assert Receipt.objects.filter(lot=lot).count() == 1


def test_due_lot_batch_isolates_corrupt_lot_and_settles_following_lot(
    lot, bidder, seller, other_catalog_item
) -> None:
    bad_wallet = fund(bidder)
    fund(seller)
    bad_bid = place_bid(
        lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00")
    )
    Bid.objects.filter(pk=bad_bid.pk).update(amount=Decimal("1001.00"))
    Lot.objects.filter(pk=lot.pk).update(
        ends_at=timezone.now() - timedelta(seconds=1)
    )
    now = timezone.now()
    good_lot = create_lot(
        seller=seller,
        catalog_item=other_catalog_item,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        starting_bid=Decimal("200.00"),
        min_increment=Decimal("10.00"),
        cache_image=False,
    )
    Lot.objects.filter(pk=good_lot.pk).update(
        ends_at=now - timedelta(seconds=1)
    )

    assert settle_due_lots(batch_size=2) == 2

    lot.refresh_from_db()
    good_lot.refresh_from_db()
    assert lot.settlement_error
    assert lot.settled_at is None
    assert good_lot.settled_at is not None
    assert bad_wallet.balance == Decimal("10000.00")
