"""Testes do ciclo de vida e dos limites do ticker de liquidação."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from decimal import Decimal
from threading import Event
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import connections
from django.test import override_settings
from django.utils import timezone

from auctions.models import Bid, Lot
from auctions.services.bidding import place_bid
from auctions.services.lots import create_lot
from core.asgi import _lifespan
from core.settlement_ticker import tick
from wallet.models import Wallet

if TYPE_CHECKING:
    from asgiref.typing import ASGIReceiveEvent, ASGISendEvent

pytestmark = pytest.mark.django_db(transaction=True)


def test_tick_respects_configured_batch_limit() -> None:
    with (
        override_settings(SETTLEMENT_BATCH_SIZE=3),
        patch(
            "core.settlement_ticker.settle_due_lots", return_value=2
        ) as settle,
    ):
        assert tick() == 2

    settle.assert_called_once_with(batch_size=3)
    assert cache.get("settlement:last_processed") == 2


def test_tick_isolates_bad_lot_and_processes_next_lot(
    lot, seller, bidder, other_catalog_item
) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))
    bid = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    Bid.objects.filter(pk=bid.pk).update(amount=Decimal("1001.00"))
    now = timezone.now()
    good_lot = create_lot(
        seller=seller,
        catalog_item=other_catalog_item,
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        starting_bid=Decimal("200.00"),
        min_increment=Decimal("10.00"),
        cache_image=False,
    )
    Lot.objects.filter(pk__in=(lot.pk, good_lot.pk)).update(ends_at=now)

    with override_settings(SETTLEMENT_BATCH_SIZE=2):
        assert tick() == 2

    lot.refresh_from_db()
    good_lot.refresh_from_db()
    assert lot.settlement_error
    assert good_lot.settled_at is not None
    assert cache.get("settlement:blocked_count") == 1
    assert cache.get("settlement:due_count") == 0


def test_enabled_ticker_processes_due_lot_during_lifespan_startup(lot) -> None:
    Lot.objects.filter(pk=lot.pk).update(ends_at=timezone.now())
    tick_finished = Event()
    original_tick = tick

    def tracked_tick() -> int:
        try:
            return original_tick()
        finally:
            connections.close_all()
            tick_finished.set()

    async def run() -> list[dict[str, str]]:
        received: list[dict[str, str]] = [{"type": "lifespan.startup"}]
        sent: list[dict[str, str]] = []

        async def receive() -> ASGIReceiveEvent:
            if received:
                return cast("ASGIReceiveEvent", received.pop(0))
            await asyncio.to_thread(tick_finished.wait, 5)
            return cast("ASGIReceiveEvent", {"type": "lifespan.shutdown"})

        async def send(message: ASGISendEvent) -> None:
            sent.append(cast("dict[str, str]", message))

        with (
            override_settings(
                ENABLE_SETTLEMENT_TICKER=True,
                SETTLEMENT_INTERVAL_SECONDS=3600,
            ),
            patch("core.asgi.ticker.tick", side_effect=tracked_tick),
        ):
            await _lifespan(receive, send)
        return sent

    sent = asyncio.run(run())
    assert tick_finished.is_set()
    lot.refresh_from_db()
    assert lot.settled_at is not None
    assert sent == [
        {"type": "lifespan.startup.complete"},
        {"type": "lifespan.shutdown.complete"},
    ]
