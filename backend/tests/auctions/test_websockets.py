"""Testes de contrato e publicação de eventos WebSocket."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict, cast
from unittest.mock import patch

import pytest
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.signing import TimestampSigner
from django.db import transaction
from django.test import override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from auctions.models import Lot
from auctions.services.bidding import place_bid
from auctions.services.lots import cancel_lot
from auctions.services.settlement import settle_lot
from core.asgi import _lifespan, application
from users.models import User
from wallet.models import Wallet

if TYPE_CHECKING:
    from uuid import UUID

    from asgiref.typing import ASGIReceiveEvent, ASGISendEvent

pytestmark = pytest.mark.django_db(transaction=True)
ALLOWED_ORIGIN = (b"origin", b"http://localhost:5173")


class EventPayload(TypedDict, total=False):
    event: str
    lot_id: str
    state_version: int
    my_position: dict[str, str | bool | int | None] | None
    ends_at: str


def issue_ticket(user: User) -> str:
    return TimestampSigner(salt="auction-ws-ticket").sign_object(
        {"purpose": "ws", "user_id": str(user.pk)}
    )


def fund(user: User) -> None:
    wallet = Wallet.objects.get(user=user)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))


def force_rollback() -> None:
    raise RuntimeError


def test_lot_consumer_sends_snapshot_and_committed_bid_event(
    lot, bidder
) -> None:
    fund(bidder)
    ticket = issue_ticket(bidder)

    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected
        snapshot = cast("EventPayload", await communicator.receive_json_from())
        assert snapshot["event"] == "lot.snapshot"
        assert snapshot["state_version"] == 1
        position = snapshot["my_position"]
        assert position is not None
        assert position["status"] == "no_bid"
        assert position["rank"] is None
        assert await communicator.receive_nothing(timeout=0.05)

        await database_sync_to_async(place_bid)(
            lot_id=lot.pk,
            bidder=bidder,
            amount=Decimal("1000.00"),
        )

        event = cast("EventPayload", await communicator.receive_json_from())
        assert event["event"] == "bid.accepted"
        assert event["state_version"] == 2
        await communicator.disconnect()

    async_to_sync(run)()


def test_lot_consumer_omits_user_position_for_anonymous(lot) -> None:
    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected
        try:
            snapshot = cast(
                "EventPayload", await communicator.receive_json_from()
            )
            assert snapshot["event"] == "lot.snapshot"
            assert "my_position" in snapshot
            assert snapshot["my_position"] is None
        finally:
            await communicator.disconnect()

    async_to_sync(run)()


def test_lot_consumer_does_not_broadcast_rolled_back_bid(lot, bidder) -> None:
    fund(bidder)
    ticket = issue_ticket(bidder)

    def rollback_bid() -> None:
        try:
            with transaction.atomic():
                place_bid(
                    lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00")
                )
                force_rollback()
        except RuntimeError:
            return

    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected
        await communicator.receive_json_from()
        await database_sync_to_async(rollback_bid)()
        assert await communicator.receive_nothing(timeout=0.1)
        await communicator.disconnect()

    async_to_sync(run)()


def test_channel_layer_failure_does_not_undo_accepted_bid(lot, bidder) -> None:
    fund(bidder)
    with patch("auctions.events.get_channel_layer", side_effect=RuntimeError):
        bid = place_bid(
            lot_id=lot.pk,
            bidder=bidder,
            amount=Decimal("1000.00"),
        )

    lot.refresh_from_db()
    assert bid.sequence == 1
    assert lot.current_bid == Decimal("1000.00")


def test_notifications_reject_expired_ticket(bidder) -> None:
    ticket = issue_ticket(bidder)

    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/notifications/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        connected, close_code = await communicator.connect()
        assert not connected
        assert close_code == 4401

    with override_settings(WS_TICKET_MAX_AGE_SECONDS=-1):
        async_to_sync(run)()


def test_public_room_treats_expired_ticket_as_anonymous(lot, bidder) -> None:
    ticket = issue_ticket(bidder)

    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected
        try:
            snapshot = cast(
                "EventPayload", await communicator.receive_json_from()
            )
            assert snapshot["event"] == "lot.snapshot"
            assert snapshot["my_position"] is None
        finally:
            await communicator.disconnect()

    with override_settings(WS_TICKET_MAX_AGE_SECONDS=-1):
        async_to_sync(run)()


def test_user_outbid_notification_is_sent_after_commit(lot, bidder) -> None:
    other = User.objects.create_user(
        email="ws-other@example.com", password="pass-123456", role="BIDDER"
    )
    fund(bidder)
    fund(other)
    first_bid = place_bid(
        lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00")
    )
    bidder_ticket = issue_ticket(bidder)

    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/notifications/?ticket={bidder_ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected

        await database_sync_to_async(place_bid)(
            lot_id=lot.pk,
            bidder=other,
            amount=Decimal("1100.00"),
        )

        event = cast("EventPayload", await communicator.receive_json_from())
        assert event["event"] == "user.outbid"
        assert event["state_version"] == 3
        assert event["lot_id"] == str(lot.pk)
        await communicator.disconnect()

    assert first_bid.sequence == 1
    async_to_sync(run)()


def test_settlement_publishes_closed_and_winner_events(lot, bidder) -> None:
    fund(bidder)
    ticket = issue_ticket(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))

    async def run() -> None:
        lot_communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        user_communicator = WebsocketCommunicator(
            application,
            f"/ws/notifications/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        lot_connected, _ = await lot_communicator.connect()
        user_connected, _ = await user_communicator.connect()
        assert lot_connected
        assert user_connected
        try:
            snapshot = cast(
                "EventPayload", await lot_communicator.receive_json_from()
            )
            assert snapshot["state_version"] == 2
            await database_sync_to_async(_expire_lot)(lot.pk)
            receipt = await database_sync_to_async(settle_lot)(lot.pk)
            assert receipt is not None
            close_event = cast(
                "EventPayload", await lot_communicator.receive_json_from()
            )
            won_event = cast(
                "EventPayload", await user_communicator.receive_json_from()
            )
            assert close_event["event"] == "lot.closed"
            assert close_event["state_version"] == 3
            assert won_event["event"] == "user.won"
            assert won_event["state_version"] == 3
            assert won_event["lot_id"] == str(lot.pk)
            assert "email" not in won_event
        finally:
            await lot_communicator.disconnect()
            await user_communicator.disconnect()

    async_to_sync(run)()


def test_lot_extension_emits_separate_versioned_event(lot, bidder) -> None:
    lot.ends_at = timezone.now() + timedelta(seconds=30)
    lot.save(update_fields=("ends_at",))
    fund(bidder)
    ticket = issue_ticket(bidder)

    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/?ticket={ticket}",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected
        try:
            await communicator.receive_json_from()
            await database_sync_to_async(place_bid)(
                lot_id=lot.pk,
                bidder=bidder,
                amount=Decimal("1000.00"),
            )
            accepted = cast(
                "EventPayload", await communicator.receive_json_from()
            )
            extended = cast(
                "EventPayload", await communicator.receive_json_from()
            )
            assert accepted["event"] == "bid.accepted"
            assert extended["event"] == "lot.extended"
            assert accepted["state_version"] == 2
            assert extended["state_version"] == 2
            assert parse_datetime(extended["ends_at"]) > lot.ends_at
        finally:
            await communicator.disconnect()

    async_to_sync(run)()


def test_cancellation_broadcasts_after_commit(lot, seller) -> None:
    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/",
            headers=[ALLOWED_ORIGIN],
        )
        connected, _subprotocol = await communicator.connect()
        assert connected
        try:
            await communicator.receive_json_from()
            await database_sync_to_async(cancel_lot)(
                lot_id=lot.pk, seller=seller, reason="teste"
            )
            event = cast(
                "EventPayload", await communicator.receive_json_from()
            )
            assert event["event"] == "lot.cancelled"
            assert event["state_version"] == 2
        finally:
            await communicator.disconnect()

    async_to_sync(run)()


def test_ticker_lifespan_starts_and_stops_task() -> None:
    async def run() -> None:
        received = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        sent: list[dict[str, str]] = []

        async def receive() -> ASGIReceiveEvent:
            return cast("ASGIReceiveEvent", received.pop(0))

        async def send(message: ASGISendEvent) -> None:
            sent.append(cast("dict[str, str]", message))

        with override_settings(ENABLE_SETTLEMENT_TICKER=False):
            await _lifespan(receive, send)

        assert sent == [
            {"type": "lifespan.startup.complete"},
            {"type": "lifespan.shutdown.complete"},
        ]

    async_to_sync(run)()


def _expire_lot(lot_id: UUID) -> None:
    Lot.objects.filter(pk=lot_id).update(ends_at=timezone.now())


def test_disallowed_websocket_origin_is_rejected(lot) -> None:
    async def run() -> None:
        communicator = WebsocketCommunicator(
            application,
            f"/ws/lots/{lot.pk}/",
            headers=[(b"origin", b"https://untrusted.invalid")],
        )
        connected, _close_code = await communicator.connect()
        assert not connected

    async_to_sync(run)()
