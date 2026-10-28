"""Batch do ticker e indicadores de saúde locais."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from auctions.models import Lot
from auctions.services.settlement import settle_due_lots


def tick() -> int:
    """Executa uma rodada e atualiza contagens sem dados pessoais."""
    cache.set(
        "settlement:last_run_at", timezone.now().isoformat(), timeout=None
    )
    processed = settle_due_lots(batch_size=settings.SETTLEMENT_BATCH_SIZE)
    cache.set(
        "settlement:last_success_at", timezone.now().isoformat(), timeout=None
    )
    cache.set("settlement:last_processed", processed, timeout=None)
    cache.set(
        "settlement:blocked_count",
        Lot.objects.filter(settlement_error__gt="").count(),
        timeout=None,
    )
    due = Lot.objects.filter(
        settled_at__isnull=True,
        cancelled_at__isnull=True,
        settlement_error="",
        ends_at__lte=timezone.now(),
    ).count()
    cache.set("settlement:due_count", due, timeout=None)
    return processed
