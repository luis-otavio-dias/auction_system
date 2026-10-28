"""Serializers do app de leilões."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, cast
from uuid import UUID

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from auctions.models import Bid, CatalogItem, Lot, Receipt
from auctions.services.lots import create_lot

if TYPE_CHECKING:
    from rest_framework.request import Request

    from users.models import User

type LotCreateData = dict[str, datetime | Decimal | CatalogItem]
type BidCreateData = dict[str, Decimal | UUID | None]


def _public_url(request: Request | None, value: str) -> str:
    """Resolve URLs relativas de mídia contra o host da API."""
    if not value or value.startswith(("http://", "https://", "//", "data:")):
        return value
    if request is None:
        return value
    return request.build_absolute_uri(value)


class CatalogItemSerializer(serializers.ModelSerializer[CatalogItem]):
    """Snapshot público de um item do catálogo externo."""

    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = CatalogItem
        fields = (
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
            "fetched_at",
        )
        read_only_fields = fields

    def get_image_url(self, obj: CatalogItem) -> str:
        return _public_url(self.context.get("request"), obj.image_url)

    def get_thumbnail_url(self, obj: CatalogItem) -> str:
        return _public_url(self.context.get("request"), obj.thumbnail_url)


class CatalogSearchQuerySerializer(
    serializers.Serializer[dict[str, str | int]]
):
    """Parâmetros aceitos na busca do catálogo."""

    q = serializers.CharField(min_length=1, max_length=200)
    limit = serializers.IntegerField(min_value=1, max_value=50, default=20)


class LotListSerializer(serializers.ModelSerializer[Lot]):
    """Resumo de lote exibido na vitrine."""

    status = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    minimum_bid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    seller_alias = serializers.CharField(
        source="seller.public_alias",
        read_only=True,
    )

    class Meta:
        model = Lot
        fields = (
            "id",
            "code",
            "status",
            "title",
            "image_url",
            "category",
            "starting_bid",
            "current_bid",
            "min_increment",
            "minimum_bid",
            "starts_at",
            "ends_at",
            "bids_count",
            "state_version",
            "seller_alias",
        )
        read_only_fields = fields

    def get_status(self, obj: Lot) -> str:
        return str(obj.status)

    def get_image_url(self, obj: Lot) -> str:
        return _public_url(self.context.get("request"), obj.image_url)


class LotDetailSerializer(serializers.ModelSerializer[Lot]):
    """Detalhe público de um lote."""

    status = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    minimum_bid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    seller_alias = serializers.CharField(
        source="seller.public_alias",
        read_only=True,
    )
    my_position = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()

    class Meta:
        model = Lot
        fields = (
            "id",
            "code",
            "status",
            "title",
            "description",
            "image_url",
            "source",
            "external_id",
            "source_url",
            "category",
            "attributes",
            "starting_bid",
            "min_increment",
            "current_bid",
            "minimum_bid",
            "starts_at",
            "ends_at",
            "original_ends_at",
            "extension_count",
            "bids_count",
            "state_version",
            "seller_alias",
            "my_position",
            "server_time",
        )
        read_only_fields = fields

    def _now(self) -> datetime:
        now = self.context.get("now")
        if isinstance(now, datetime):
            return now
        return timezone.now()

    def get_status(self, obj: Lot) -> str:
        return str(obj.status_at(self._now()))

    def get_image_url(self, obj: Lot) -> str:
        return _public_url(self.context.get("request"), obj.image_url)

    def get_my_position(
        self, obj: Lot
    ) -> dict[str, str | bool | int | None] | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        last = obj.bids.filter(bidder_id=user.pk).order_by("-sequence").first()
        leading = obj.current_winner_id == user.pk
        rank = (
            1 + obj.bids.filter(sequence__gt=last.sequence).count()
            if last is not None and not leading
            else 1
            if leading
            else None
        )
        return {
            "is_leading": leading,
            "status": "leading" if leading else "outbid" if last else "no_bid",
            "last_amount": f"{last.amount:.2f}" if last else None,
            "rank": 1 if leading else rank,
        }

    def get_server_time(self, _obj: Lot) -> str:
        return self._now().isoformat()


class LotFilterSerializer(serializers.Serializer[dict[str, str]]):
    """Filtros e ordenação aceitos pela vitrine."""

    tab = serializers.ChoiceField(
        choices=("live", "scheduled", "ended"),
        required=False,
        allow_blank=True,
        default="",
    )
    q = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="",
    )
    category = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    sort = serializers.ChoiceField(
        choices=("ending", "price-high", "price-low", "recent"),
        required=False,
        allow_blank=True,
        default="ending",
    )


class LotCreateSerializer(serializers.ModelSerializer[Lot]):
    """Criação de lote a partir de um item de catálogo persistido."""

    catalog_item_id = serializers.PrimaryKeyRelatedField(
        queryset=CatalogItem.objects.all(),
        source="catalog_item",
    )
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    starting_bid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    min_increment = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    class Meta:
        model = Lot
        fields = (
            "catalog_item_id",
            "starts_at",
            "ends_at",
            "starting_bid",
            "min_increment",
        )

    def validate(self, attrs: LotCreateData) -> LotCreateData:
        starts_at = cast("datetime", attrs["starts_at"])
        ends_at = cast("datetime", attrs["ends_at"])
        if starts_at >= ends_at:
            message = "O início deve ser anterior ao término do lote."
            raise serializers.ValidationError({"ends_at": message})
        if ends_at <= timezone.now():
            message = "O término do lote deve estar no futuro."
            raise serializers.ValidationError({"ends_at": message})
        return attrs

    def create(self, validated_data: LotCreateData) -> Lot:
        seller = cast("User", self.context["seller"])
        return create_lot(
            seller=seller,
            catalog_item=cast("CatalogItem", validated_data["catalog_item"]),
            starts_at=cast("datetime", validated_data["starts_at"]),
            ends_at=cast("datetime", validated_data["ends_at"]),
            starting_bid=cast("Decimal", validated_data["starting_bid"]),
            min_increment=cast("Decimal", validated_data["min_increment"]),
        )


class LotCancelSerializer(serializers.Serializer[dict[str, str]]):
    """Corpo do cancelamento de lote."""

    reason = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default="",
    )


class BidCreateSerializer(serializers.Serializer[BidCreateData]):
    """Corpo de um lance."""

    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    client_bid_id = serializers.UUIDField(required=False, allow_null=True)


class BidSerializer(serializers.ModelSerializer[Bid]):
    """Representação pública de um lance."""

    is_mine = serializers.SerializerMethodField()
    lot_id = serializers.UUIDField(read_only=True)
    lot_code = serializers.CharField(source="lot.code", read_only=True)
    lot_title = serializers.CharField(source="lot.title", read_only=True)

    class Meta:
        model = Bid
        fields = (
            "sequence",
            "amount",
            "bidder_alias",
            "placed_at",
            "is_mine",
            "lot_id",
            "lot_code",
            "lot_title",
        )
        read_only_fields = fields

    def get_is_mine(self, obj: Bid) -> bool | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None
        return obj.bidder_id == user.pk

    def get_fields(self) -> dict[str, serializers.Field]:
        fields = super().get_fields()
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            fields.pop("is_mine", None)
        return fields


class ReceiptSerializer(serializers.ModelSerializer[Receipt]):
    """Snapshot público imutável do comprovante."""

    share_url = serializers.SerializerMethodField()
    item_image_url = serializers.SerializerMethodField()

    def get_share_url(self, obj: Receipt) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/comprovantes/{obj.token}"

    def get_item_image_url(self, obj: Receipt) -> str:
        return _public_url(self.context.get("request"), obj.item_image_url)

    class Meta:
        model = Receipt
        fields = (
            "token",
            "code",
            "winner_alias",
            "seller_alias",
            "lot_code",
            "item_source",
            "item_external_id",
            "item_title",
            "item_image_url",
            "final_price",
            "issued_at",
            "share_url",
            "audit_head",
            "bid_count",
            "hash_version",
        )
        read_only_fields = fields
