"""Modelos do domínio de carteira."""

import uuid
from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Wallet(models.Model):
    """Carteira financeira de um usuário."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="wallet",
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    committed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "carteira"
        verbose_name_plural = "carteiras"
        constraints = (
            models.CheckConstraint(
                condition=Q(balance__gte=0),
                name="balance_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(committed__gte=0),
                name="committed_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(committed__lte=F("balance")),
                name="committed_lte_balance",
            ),
        )

    def __str__(self) -> str:
        return f"Carteira de {self.user_id}"

    @property
    def available(self) -> Decimal:
        """Saldo livre para novos compromissos."""
        return self.balance - self.committed


class WalletTransaction(models.Model):
    """Lançamento append-only do livro-razão da carteira."""

    class Type(models.TextChoices):
        DEPOSIT = "DEPOSIT", "Depósito"
        BID_HOLD = "BID_HOLD", "Reserva de lance"
        BID_RELEASE = "BID_RELEASE", "Liberação de reserva de lance"
        SETTLEMENT_DEBIT = "SETTLEMENT_DEBIT", "Débito de liquidação"
        SETTLEMENT_CREDIT = "SETTLEMENT_CREDIT", "Crédito de liquidação"
        CANCELLATION_RELEASE = (
            "CANCELLATION_RELEASE",
            "Liberação por cancelamento",
        )
        ADJUSTMENT_CREDIT = "ADJUSTMENT_CREDIT", "Ajuste de crédito"
        ADJUSTMENT_DEBIT = "ADJUSTMENT_DEBIT", "Ajuste de débito"

    class ReferenceKind(models.TextChoices):
        NONE = "NONE", "Nenhuma"
        LOT = "LOT", "Lote"
        BID = "BID", "Lance"
        DEPOSIT = "DEPOSIT", "Depósito"

    _CREDIT_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            Type.DEPOSIT,
            Type.SETTLEMENT_CREDIT,
            Type.ADJUSTMENT_CREDIT,
        },
    )
    _DEBIT_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            Type.SETTLEMENT_DEBIT,
            Type.ADJUSTMENT_DEBIT,
        },
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    type = models.CharField(max_length=20, choices=Type)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    committed_after = models.DecimalField(max_digits=12, decimal_places=2)
    reference_kind = models.CharField(
        max_length=16,
        choices=ReferenceKind,
        default=ReferenceKind.NONE,
    )
    reference_id = models.UUIDField(null=True, blank=True)
    idempotency_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
    )
    description = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "lançamento de carteira"
        verbose_name_plural = "lançamentos de carteira"
        ordering = ("-created_at",)
        constraints = (
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="wallet_tx_amount_gt_zero",
            ),
            models.UniqueConstraint(
                fields=("wallet", "idempotency_key"),
                condition=Q(idempotency_key__isnull=False),
                name="unique_wallet_idempotency_key",
            ),
        )
        indexes = (
            models.Index(
                fields=("wallet", "created_at"),
                name="wallet_tx_wallet_created_idx",
            ),
            models.Index(
                fields=("reference_kind", "reference_id"),
                name="wallet_tx_ref_idx",
            ),
        )

    def __str__(self) -> str:
        return f"{self.type} {self.amount} ({self.wallet_id})"

    @property
    def signed_amount(self) -> Decimal:
        """Valor com sinal conforme o efeito no saldo da carteira.

        Reservas e liberações alteram apenas ``committed``; por isso valem
        zero para efeito de saldo e são informadas pelo campo ``amount``.
        """
        if self.type in self._CREDIT_TYPES:
            return self.amount
        if self.type in self._DEBIT_TYPES:
            return -self.amount
        return Decimal("0.00")
