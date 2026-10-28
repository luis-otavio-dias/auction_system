"""Consultas de leitura para lotes e catálogo."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from auctions.models import CatalogItem, Lot

if TYPE_CHECKING:
    from uuid import UUID

    from django.db.models import QuerySet


def visible_lots() -> QuerySet[Lot]:
    """Lotes exibíveis na vitrine, sem cancelados."""
    return (
        Lot.objects.exclude(cancelled_at__isnull=False)
        .select_related("seller", "current_winner")
        .order_by("ends_at")
    )


def filter_lots(
    *,
    tab: str = "",
    q: str = "",
    category: str = "",
    sort: str = "ending",
) -> QuerySet[Lot]:
    """Aplica os filtros e a ordenação da vitrine."""
    now = timezone.now()
    queryset = visible_lots()

    match tab:
        case "live":
            queryset = queryset.filter(
                starts_at__lte=now,
                ends_at__gt=now,
                settled_at__isnull=True,
                cancelled_at__isnull=True,
            )
        case "scheduled":
            queryset = queryset.filter(
                starts_at__gt=now,
                settled_at__isnull=True,
                cancelled_at__isnull=True,
            )
        case "ended":
            queryset = queryset.filter(
                Q(ends_at__lte=now) | Q(settled_at__isnull=False),
                cancelled_at__isnull=True,
            )

    if q:
        queryset = queryset.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(category__icontains=q),
        )

    if category:
        queryset = queryset.filter(category__iexact=category)

    match sort:
        case "price-high" | "price-low":
            queryset = queryset.annotate(
                effective_price=Coalesce(
                    F("current_bid"),
                    F("starting_bid"),
                ),
            )
            ordering = (
                F("effective_price").desc(nulls_last=True)
                if sort == "price-high"
                else F("effective_price").asc(nulls_last=True)
            )
            return queryset.order_by(ordering, "-created_at")
        case "recent":
            return queryset.order_by("-created_at")
        case _:
            return queryset.order_by("ends_at", "-created_at")


def get_public_lot(lot_id: UUID) -> Lot | None:
    """Detalhe público de um lote, inclusive cancelado."""
    return (
        Lot.objects.select_related("seller", "current_winner")
        .filter(pk=lot_id)
        .first()
    )


def search_cached_catalog(query: str, limit: int) -> QuerySet[CatalogItem]:
    """Busca itens já persistidos, usados como fallback da AIC."""
    return CatalogItem.objects.filter(
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(category__icontains=query)
        | Q(external_id__icontains=query),
    ).order_by("-fetched_at")[:limit]
