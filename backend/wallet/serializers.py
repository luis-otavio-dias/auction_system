"""Serializers das carteiras e do livro-razão."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from wallet.models import Wallet, WalletTransaction


class WalletSerializer(serializers.ModelSerializer[Wallet]):
    """Saldo financeiro privado do usuário autenticado."""

    available = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = Wallet
        fields = ("balance", "committed", "available", "updated_at")
        read_only_fields = fields


class DepositSerializer(
    serializers.Serializer[dict[str, Decimal | str | None]]
):
    """Entrada do depósito simulado."""

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    idempotency_key = serializers.CharField(
        max_length=64, required=False, allow_blank=False
    )


class WalletTransactionSerializer(
    serializers.ModelSerializer[WalletTransaction]
):
    """Lançamento privado de carteira."""

    class Meta:
        model = WalletTransaction
        fields = (
            "id",
            "type",
            "amount",
            "balance_after",
            "committed_after",
            "reference_kind",
            "reference_id",
            "description",
            "created_at",
        )
        read_only_fields = fields
