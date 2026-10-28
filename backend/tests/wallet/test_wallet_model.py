"""Tests for the wallet model and its invariants."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.db import IntegrityError, transaction

from wallet.models import Wallet

if TYPE_CHECKING:
    from users.models import User


@pytest.mark.django_db
def test_wallet_created_automatically_for_seller(seller: User) -> None:
    assert Wallet.objects.filter(user=seller).exists()


@pytest.mark.django_db
def test_wallet_created_automatically_for_bidder(bidder: User) -> None:
    assert Wallet.objects.filter(user=bidder).exists()
    assert bidder.wallet.pk == Wallet.objects.get(user=bidder).pk


@pytest.mark.django_db
def test_wallet_starts_with_zero_balance(wallet: Wallet) -> None:
    assert wallet.balance == Decimal("0.00")
    assert wallet.committed == Decimal("0.00")
    assert wallet.available == Decimal("0.00")


@pytest.mark.django_db
def test_available_is_balance_minus_committed(wallet: Wallet) -> None:
    Wallet.objects.filter(pk=wallet.pk).update(
        balance=Decimal("1000.00"),
        committed=Decimal("250.00"),
    )

    wallet.refresh_from_db()

    assert wallet.available == Decimal("750.00")


@pytest.mark.django_db
def test_balance_cannot_be_negative(wallet: Wallet) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=Decimal("-1.00"),
        )


@pytest.mark.django_db
def test_committed_cannot_be_negative(wallet: Wallet) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Wallet.objects.filter(pk=wallet.pk).update(
            committed=Decimal("-1.00"),
        )


@pytest.mark.django_db
def test_committed_cannot_exceed_balance(wallet: Wallet) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Wallet.objects.filter(pk=wallet.pk).update(
            balance=Decimal("10.00"),
            committed=Decimal("20.00"),
        )
