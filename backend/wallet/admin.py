"""Registro dos modelos de carteira no Django Admin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from wallet.models import Wallet, WalletTransaction

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """Carteiras são somente leitura: saldos mudam apenas via serviços."""

    list_display = (
        "id",
        "user",
        "balance",
        "committed",
        "available",
        "updated_at",
    )
    list_select_related = ("user",)
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__email",)
    readonly_fields = (
        "id",
        "user",
        "balance",
        "committed",
        "available",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: Wallet | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: Wallet | None = None,
    ) -> bool:
        return False


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    """Livro-razão append-only exposto apenas para consulta."""

    list_display = (
        "created_at",
        "wallet",
        "type",
        "signed_amount",
        "amount",
        "balance_after",
        "committed_after",
        "reference_kind",
        "reference_id",
    )
    list_select_related = ("wallet", "wallet__user")
    list_filter = ("type", "reference_kind", "created_at")
    search_fields = ("wallet__user__email", "idempotency_key")
    readonly_fields = (
        "id",
        "wallet",
        "type",
        "amount",
        "balance_after",
        "committed_after",
        "reference_kind",
        "reference_id",
        "idempotency_key",
        "description",
        "metadata",
        "signed_amount",
        "created_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: WalletTransaction | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: WalletTransaction | None = None,
    ) -> bool:
        return False
