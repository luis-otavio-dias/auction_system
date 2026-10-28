"""Modelos do app de leilões."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, override

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
    from decimal import Decimal

    from django.db.models.base import ModelBase


def generate_lot_code() -> str:
    """Gera um código curto e estável para exibição do lote."""
    return f"L-{uuid.uuid4().hex[:10].upper()}"


class CatalogItem(models.Model):
    """Snapshot imutável de um item do catálogo externo."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    source = models.CharField(max_length=32, default="artic")
    external_id = models.CharField(max_length=64)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    source_url = models.URLField(max_length=500)
    category = models.CharField(max_length=100, blank=True)
    attributes = models.JSONField(default=dict)
    raw_payload = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "item de catálogo"
        verbose_name_plural = "itens de catálogo"
        ordering = ("-fetched_at",)
        constraints = (
            models.UniqueConstraint(
                fields=("source", "external_id"),
                name="catalog_unique_source_external",
            ),
        )
        indexes = (
            models.Index(fields=("source",), name="catalog_source_idx"),
            models.Index(fields=("category",), name="catalog_category_idx"),
        )

    @override
    def __str__(self) -> str:
        return f"{self.title} ({self.source}:{self.external_id})"

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            message = (
                "CatalogItem é um snapshot imutável e não pode ser atualizado."
            )
            raise ValueError(message)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class Lot(models.Model):
    """Lote imutável após a criação, exceto pelas mutações de domínio."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Agendado"
        LIVE = "live", "Ao vivo"
        ENDED = "ended", "Encerrado"
        CANCELLED = "cancelled", "Cancelado"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(
        max_length=12,
        unique=True,
        default=generate_lot_code,
        editable=False,
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lots",
    )
    catalog_item = models.ForeignKey(
        CatalogItem,
        on_delete=models.PROTECT,
        related_name="lots",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500)
    image_remote_url = models.URLField(max_length=500)
    image_cached = models.BooleanField(default=False)
    source = models.CharField(max_length=32)
    external_id = models.CharField(max_length=64)
    source_url = models.URLField(max_length=500)
    category = models.CharField(max_length=100, blank=True)
    attributes = models.JSONField(default=dict)
    starting_bid = models.DecimalField(max_digits=12, decimal_places=2)
    min_increment = models.DecimalField(max_digits=12, decimal_places=2)
    current_bid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    current_winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lots_led",
        null=True,
        blank=True,
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    original_ends_at = models.DateTimeField()
    extension_count = models.PositiveIntegerField(default=0)
    bids_count = models.PositiveIntegerField(default=0)
    history_head = models.CharField(max_length=64, blank=True)
    history_version = models.PositiveSmallIntegerField(default=1)
    state_version = models.PositiveBigIntegerField(default=1)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_lots",
        null=True,
        blank=True,
    )
    cancel_reason = models.CharField(max_length=255, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="lots_won",
        null=True,
        blank=True,
    )
    final_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    settlement_error = models.TextField(blank=True)
    settlement_checked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "lote"
        verbose_name_plural = "lotes"
        ordering = ("-created_at",)
        constraints = (
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")),
                name="lot_ends_after_starts",
            ),
            models.CheckConstraint(
                condition=Q(starting_bid__gt=0),
                name="lot_starting_bid_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(min_increment__gt=0),
                name="lot_min_increment_gt_zero",
            ),
            models.CheckConstraint(
                condition=Q(current_bid__isnull=True)
                | Q(current_bid__gte=F("starting_bid")),
                name="lot_current_bid_gte_starting",
            ),
            models.CheckConstraint(
                condition=Q(current_winner__isnull=True)
                | Q(current_bid__isnull=False),
                name="lot_winner_requires_bid",
            ),
            models.CheckConstraint(
                condition=Q(final_price__isnull=True) | Q(final_price__gte=0),
                name="lot_final_price_gte_zero",
            ),
            models.CheckConstraint(
                condition=Q(state_version__gte=1),
                name="lot_state_version_gte_one",
            ),
        )
        indexes = (
            models.Index(fields=("starts_at",), name="lot_starts_at_idx"),
            models.Index(fields=("ends_at",), name="lot_ends_at_idx"),
            models.Index(fields=("seller",), name="lot_seller_idx"),
            models.Index(fields=("category",), name="lot_category_idx"),
            models.Index(
                fields=("current_winner",),
                name="lot_current_winner_idx",
            ),
        )

    @override
    def __str__(self) -> str:
        return f"{self.code} - {self.title}"

    @property
    def minimum_bid(self) -> Decimal:
        """Menor valor aceito para o próximo lance."""
        if self.current_bid is None:
            return self.starting_bid
        return self.current_bid + self.min_increment

    @property
    def has_bids(self) -> bool:
        return self.bids_count > 0

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    @property
    def is_settled(self) -> bool:
        return self.settled_at is not None

    def status_at(self, moment: datetime) -> Status:
        """Calcula o status derivado para o instante informado."""
        if self.is_cancelled:
            return self.Status.CANCELLED
        if self.is_settled or moment >= self.ends_at:
            return self.Status.ENDED
        if moment < self.starts_at:
            return self.Status.SCHEDULED
        return self.Status.LIVE

    @property
    def status(self) -> Status:
        return self.status_at(timezone.now())


class Bid(models.Model):
    """Registro imutável de um lance aceito."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="bids")
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT
    )
    bidder_alias = models.CharField(max_length=24)
    sequence = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    placed_at = models.DateTimeField()
    prev_hash = models.CharField(max_length=64)
    content_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64)
    hash_version = models.PositiveSmallIntegerField(default=1)
    ends_at_before = models.DateTimeField()
    ends_at_after = models.DateTimeField()
    client_bid_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sequence",)
        constraints = (
            models.UniqueConstraint(
                fields=("lot", "sequence"), name="bid_lot_sequence_unique"
            ),
            models.UniqueConstraint(
                fields=("lot", "bidder", "client_bid_id"),
                condition=Q(client_bid_id__isnull=False),
                name="bid_client_id_unique",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="bid_amount_gt_zero"
            ),
            models.CheckConstraint(
                condition=Q(sequence__gt=0), name="bid_sequence_gt_zero"
            ),
        )
        indexes = (
            models.Index(fields=("bidder",), name="bid_bidder_idx"),
            models.Index(fields=("placed_at",), name="bid_placed_at_idx"),
        )

    def __str__(self) -> str:
        return f"{self.lot.code} #{self.sequence} {self.amount}"

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            message = "Bid é imutável."
            raise ValueError(message)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )


class Receipt(models.Model):
    """Comprovante imutável de liquidação de um lote."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(max_length=16, unique=True)
    lot = models.OneToOneField(
        Lot, on_delete=models.PROTECT, related_name="receipt"
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="receipts_won",
    )
    winner_alias = models.CharField(max_length=24)
    seller_alias = models.CharField(max_length=24)
    lot_code = models.CharField(max_length=12)
    item_source = models.CharField(max_length=32)
    item_external_id = models.CharField(max_length=64)
    item_title = models.CharField(max_length=300)
    item_image_url = models.URLField(max_length=500)
    final_price = models.DecimalField(max_digits=12, decimal_places=2)
    issued_at = models.DateTimeField()
    audit_head = models.CharField(max_length=64)
    bid_count = models.PositiveIntegerField()
    verification_hash = models.CharField(max_length=64)
    hash_version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-issued_at",)

    def __str__(self) -> str:
        return self.code

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        if not self._state.adding:
            message = "Receipt é imutável."
            raise ValueError(message)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
