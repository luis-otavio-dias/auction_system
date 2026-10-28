"""Registro dos modelos de leilão no Django Admin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from auctions.models import Bid, CatalogItem, Lot, Receipt

if TYPE_CHECKING:
    from django.http import HttpRequest


@admin.register(CatalogItem)
class CatalogItemAdmin(admin.ModelAdmin):
    """Itens de catálogo são snapshots imutáveis: apenas consulta."""

    list_display = (
        "title",
        "source",
        "external_id",
        "category",
        "fetched_at",
        "created_at",
    )
    list_filter = ("source", "category", "fetched_at")
    search_fields = ("title", "description", "external_id", "category")
    readonly_fields = (
        "id",
        "source",
        "external_id",
        "title",
        "description",
        "image_url",
        "thumbnail_url",
        "source_url",
        "category",
        "attributes",
        "raw_payload",
        "fetched_at",
        "created_at",
    )
    ordering = ("-fetched_at",)

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: CatalogItem | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: CatalogItem | None = None,
    ) -> bool:
        return False


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    """Lotes mudam apenas via serviços de domínio, nunca pelo admin."""

    list_display = (
        "code",
        "title",
        "seller",
        "status_display",
        "bids_count",
        "current_bid",
        "starts_at",
        "ends_at",
        "cancelled_at",
    )
    list_select_related = ("seller", "catalog_item", "current_winner")
    list_filter = (
        "category",
        "image_cached",
        "starts_at",
        "ends_at",
        "cancelled_at",
        "settled_at",
    )
    search_fields = (
        "code",
        "title",
        "description",
        "external_id",
        "seller__email",
    )
    readonly_fields = (
        "id",
        "code",
        "seller",
        "catalog_item",
        "title",
        "description",
        "image_url",
        "image_remote_url",
        "image_cached",
        "source",
        "external_id",
        "source_url",
        "category",
        "attributes",
        "starting_bid",
        "min_increment",
        "current_bid",
        "current_winner",
        "minimum_bid",
        "starts_at",
        "ends_at",
        "original_ends_at",
        "extension_count",
        "bids_count",
        "history_head",
        "history_version",
        "state_version",
        "cancelled_at",
        "cancelled_by",
        "cancel_reason",
        "settled_at",
        "winner",
        "final_price",
        "settlement_error",
        "settlement_checked_at",
        "status_display",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    @admin.display(description="Status", ordering="ends_at")
    def status_display(self, obj: Lot) -> str:
        return str(obj.status.label)

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        _request: HttpRequest,
        _obj: Lot | None = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        _request: HttpRequest,
        _obj: Lot | None = None,
    ) -> bool:
        return False


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    """Lances imutáveis disponíveis apenas para consulta."""

    list_display = ("lot", "sequence", "bidder_alias", "amount", "placed_at")
    list_select_related = ("lot",)
    readonly_fields = (
        "id",
        "lot",
        "bidder",
        "bidder_alias",
        "sequence",
        "amount",
        "client_bid_id",
        "placed_at",
        "ends_at_before",
        "ends_at_after",
        "prev_hash",
        "content_hash",
        "hash",
        "hash_version",
    )
    ordering = ("lot", "sequence")

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, _request: HttpRequest, _obj: Bid | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, _request: HttpRequest, _obj: Bid | None = None
    ) -> bool:
        return False


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    """Comprovantes imutáveis disponíveis apenas para consulta."""

    list_display = (
        "code",
        "lot_code",
        "winner_alias",
        "final_price",
        "issued_at",
    )
    readonly_fields = (
        "id",
        "token",
        "code",
        "lot",
        "winner",
        "winner_alias",
        "seller_alias",
        "lot_code",
        "item_source",
        "item_external_id",
        "item_title",
        "item_image_url",
        "final_price",
        "issued_at",
        "audit_head",
        "bid_count",
        "verification_hash",
        "hash_version",
    )
    ordering = ("-issued_at",)

    def has_add_permission(self, _request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, _request: HttpRequest, _obj: Receipt | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, _request: HttpRequest, _obj: Receipt | None = None
    ) -> bool:
        return False
