"""Serviços de domínio da carteira."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db import transaction

from wallet.models import Wallet, WalletTransaction

if TYPE_CHECKING:
    from decimal import Decimal
    from uuid import UUID


class WalletError(Exception):
    """Erro base das operações de carteira."""


class InvalidAmountError(WalletError):
    """Valor de operação inválido."""

    def __init__(self, amount: Decimal) -> None:
        self.amount = amount
        super().__init__(
            f"Valor inválido para operação: {amount}. "
            "O valor deve ser positivo e finito.",
        )


class IdempotencyConflictError(WalletError):
    """Chave de idempotência reutilizada com conteúdo divergente."""

    def __init__(
        self,
        idempotency_key: str,
        existing_amount: Decimal,
        amount: Decimal,
    ) -> None:
        self.idempotency_key = idempotency_key
        self.existing_amount = existing_amount
        self.amount = amount
        super().__init__(
            f"Chave de idempotência {idempotency_key!r} já foi usada "
            f"com o valor {existing_amount}, não com {amount}.",
        )


class InsufficientAvailableError(WalletError):
    """Saldo livre insuficiente para a reserva."""


class InsufficientCommittedError(WalletError):
    """Reserva ativa insuficiente para liberação."""


@dataclass(frozen=True)
class DepositResult:
    """Lançamento de depósito e indicação de replay idempotente."""

    transaction: WalletTransaction
    replayed: bool


def _validate_amount(amount: Decimal) -> None:
    if not amount.is_finite() or amount <= 0:
        raise InvalidAmountError(amount)


def deposit(
    wallet_id: UUID,
    amount: Decimal,
    idempotency_key: str | None = None,
    description: str = "",
) -> DepositResult:
    """Registra um depósito e devolve o lançamento criado.

    A chave de idempotência é consultada dentro da transação, depois do
    lock da carteira, para que um retry não movimente o saldo novamente.
    """
    _validate_amount(amount)

    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet_id)

        if idempotency_key is not None:
            existing = WalletTransaction.objects.filter(
                wallet=wallet,
                idempotency_key=idempotency_key,
            ).first()
            if existing is not None:
                if (
                    existing.type == WalletTransaction.Type.DEPOSIT
                    and existing.amount == amount
                ):
                    return DepositResult(existing, replayed=True)
                raise IdempotencyConflictError(
                    idempotency_key,
                    existing.amount,
                    amount,
                )

        wallet.balance += amount
        wallet.save(update_fields=("balance", "updated_at"))

        created = WalletTransaction.objects.create(
            wallet=wallet,
            type=WalletTransaction.Type.DEPOSIT,
            amount=amount,
            balance_after=wallet.balance,
            committed_after=wallet.committed,
            reference_kind=WalletTransaction.ReferenceKind.DEPOSIT,
            reference_id=None,
            idempotency_key=idempotency_key,
            description=description,
        )
        return DepositResult(created, replayed=False)


def hold(
    wallet_id: UUID,
    amount: Decimal,
    *,
    reference_id: UUID,
    idempotency_key: str,
) -> WalletTransaction:
    """Reserva saldo disponível para um lance."""
    _validate_amount(amount)
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet_id)
        existing = WalletTransaction.objects.filter(
            wallet=wallet, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            if (
                existing.type == WalletTransaction.Type.BID_HOLD
                and existing.amount == amount
            ):
                return existing
            raise IdempotencyConflictError(
                idempotency_key, existing.amount, amount
            )
        if wallet.available < amount:
            raise InsufficientAvailableError
        wallet.committed += amount
        wallet.save(update_fields=("committed", "updated_at"))
        return WalletTransaction.objects.create(
            wallet=wallet,
            type=WalletTransaction.Type.BID_HOLD,
            amount=amount,
            balance_after=wallet.balance,
            committed_after=wallet.committed,
            reference_kind=WalletTransaction.ReferenceKind.BID,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )


def release(
    wallet_id: UUID,
    amount: Decimal,
    *,
    reference_id: UUID,
    idempotency_key: str,
) -> WalletTransaction:
    """Libera saldo reservado por um lance superado."""
    _validate_amount(amount)
    with transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(pk=wallet_id)
        existing = WalletTransaction.objects.filter(
            wallet=wallet, idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            if (
                existing.type == WalletTransaction.Type.BID_RELEASE
                and existing.amount == amount
            ):
                return existing
            raise IdempotencyConflictError(
                idempotency_key, existing.amount, amount
            )
        if wallet.committed < amount:
            raise InsufficientCommittedError
        wallet.committed -= amount
        wallet.save(update_fields=("committed", "updated_at"))
        return WalletTransaction.objects.create(
            wallet=wallet,
            type=WalletTransaction.Type.BID_RELEASE,
            amount=amount,
            balance_after=wallet.balance,
            committed_after=wallet.committed,
            reference_kind=WalletTransaction.ReferenceKind.BID,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )


@transaction.atomic
def settle_debit(
    wallet: Wallet, amount: Decimal, lot_id: UUID, bid_id: UUID
) -> WalletTransaction:
    """Debita preço final e consome a reserva do lance vencedor."""
    _validate_amount(amount)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if locked.balance < amount or locked.committed < amount:
        raise InsufficientCommittedError
    locked.balance -= amount
    locked.committed -= amount
    locked.save(update_fields=("balance", "committed", "updated_at"))
    return WalletTransaction.objects.create(
        wallet=locked,
        type=WalletTransaction.Type.SETTLEMENT_DEBIT,
        amount=amount,
        balance_after=locked.balance,
        committed_after=locked.committed,
        reference_kind=WalletTransaction.ReferenceKind.BID,
        reference_id=bid_id,
        description=f"Liquidação do lote {lot_id}",
    )


@transaction.atomic
def settle_credit(
    wallet: Wallet, amount: Decimal, lot_id: UUID
) -> WalletTransaction:
    """Credita o preço final na carteira do leiloeiro."""
    _validate_amount(amount)
    locked = Wallet.objects.select_for_update().get(pk=wallet.pk)
    locked.balance += amount
    locked.save(update_fields=("balance", "updated_at"))
    return WalletTransaction.objects.create(
        wallet=locked,
        type=WalletTransaction.Type.SETTLEMENT_CREDIT,
        amount=amount,
        balance_after=locked.balance,
        committed_after=locked.committed,
        reference_kind=WalletTransaction.ReferenceKind.LOT,
        reference_id=lot_id,
        description=f"Crédito da liquidação do lote {lot_id}",
    )
