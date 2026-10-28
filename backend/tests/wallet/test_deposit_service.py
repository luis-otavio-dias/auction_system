"""Tests for the wallet deposit service."""

from decimal import Decimal

import pytest

from wallet.models import Wallet, WalletTransaction
from wallet.services import (
    IdempotencyConflictError,
    InvalidAmountError,
    deposit,
)


@pytest.mark.django_db
def test_deposit_updates_wallet_and_creates_transaction(
    wallet: Wallet,
) -> None:
    result = deposit(wallet.pk, Decimal("150.00"))
    transaction = result.transaction

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("150.00")
    assert wallet.committed == Decimal("0.00")
    assert wallet.available == Decimal("150.00")
    assert transaction.type == WalletTransaction.Type.DEPOSIT
    assert transaction.amount == Decimal("150.00")
    assert transaction.balance_after == Decimal("150.00")
    assert transaction.committed_after == Decimal("0.00")
    assert transaction.wallet_id == wallet.pk
    assert WalletTransaction.objects.filter(pk=transaction.pk).exists()


@pytest.mark.django_db
def test_deposit_with_same_idempotency_key_returns_original(
    wallet: Wallet,
) -> None:
    first = deposit(
        wallet.pk,
        Decimal("50.00"),
        idempotency_key="deposit-1",
    )
    second = deposit(
        wallet.pk,
        Decimal("50.00"),
        idempotency_key="deposit-1",
    )

    wallet.refresh_from_db()

    assert second.transaction.pk == first.transaction.pk
    assert second.replayed
    assert second.transaction.balance_after == Decimal("50.00")
    assert wallet.balance == Decimal("50.00")
    assert WalletTransaction.objects.filter(wallet=wallet).count() == 1


@pytest.mark.django_db
def test_deposit_with_reused_key_and_different_amount_conflicts(
    wallet: Wallet,
) -> None:
    deposit(
        wallet.pk,
        Decimal("10.00"),
        idempotency_key="deposit-2",
    )

    with pytest.raises(IdempotencyConflictError):
        deposit(
            wallet.pk,
            Decimal("20.00"),
            idempotency_key="deposit-2",
        )

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("10.00")
    assert WalletTransaction.objects.filter(wallet=wallet).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("amount", [Decimal("0.00"), Decimal("-10.00")])
def test_deposit_rejects_non_positive_amount(
    wallet: Wallet,
    amount: Decimal,
) -> None:
    with pytest.raises(InvalidAmountError):
        deposit(wallet.pk, amount)

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("0.00")
    assert not WalletTransaction.objects.filter(wallet=wallet).exists()


@pytest.mark.django_db
def test_deposit_persists_description(wallet: Wallet) -> None:
    result = deposit(
        wallet.pk,
        Decimal("75.50"),
        description="Depósito inicial",
    )

    transaction = result.transaction
    transaction.refresh_from_db()

    assert transaction.description == "Depósito inicial"
