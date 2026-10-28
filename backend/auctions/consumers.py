"""Consumers de sala pública e notificações pessoais."""

from __future__ import annotations

import asyncio
from datetime import UTC
from typing import TYPE_CHECKING, TypedDict, cast

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from auctions.models import Lot

if TYPE_CHECKING:
    from uuid import UUID

    from users.models import User

type EventValue = str | int | bool | None


class Position(TypedDict):
    is_leading: bool
    status: str
    last_amount: str | None
    rank: int | None


class LotSnapshot(TypedDict):
    event: str
    lot_id: str
    code: str
    title: str
    status: str
    current_bid: str | None
    minimum_bid: str
    ends_at: str
    bids_count: int
    state_version: int
    server_time: str
    my_position: Position | None


@database_sync_to_async
def _lot_snapshot(lot_id: UUID, user_id: UUID | None) -> LotSnapshot | None:
    lot = (
        Lot.objects.select_related("seller", "current_winner")
        .filter(pk=lot_id)
        .first()
    )
    if lot is None:
        return None
    position: Position | None = None
    if user_id is not None:
        last_bid = (
            lot.bids.filter(bidder_id=user_id).order_by("-sequence").first()
        )
        is_leading = lot.current_winner_id == user_id
        position = {
            "is_leading": is_leading,
            "status": "leading"
            if is_leading
            else "outbid"
            if last_bid
            else "no_bid",
            "last_amount": f"{last_bid.amount:.2f}" if last_bid else None,
            "rank": (
                1 + lot.bids.filter(sequence__gt=last_bid.sequence).count()
                if last_bid is not None and not is_leading
                else 1
                if is_leading
                else None
            ),
        }
    now = timezone.now()
    return {
        "event": "lot.snapshot",
        "lot_id": str(lot.pk),
        "code": lot.code,
        "title": lot.title,
        "status": str(lot.status_at(now)),
        "current_bid": f"{lot.current_bid:.2f}"
        if lot.current_bid is not None
        else None,
        "minimum_bid": f"{lot.minimum_bid:.2f}",
        "ends_at": lot.ends_at.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "bids_count": lot.bids_count,
        "state_version": lot.state_version,
        "server_time": now.astimezone(UTC)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
        "my_position": position,
    }


class LotConsumer(AsyncJsonWebsocketConsumer):
    """Sala aberta com snapshot e eventos do lote."""

    async def connect(self) -> None:
        route_data = cast(
            "dict[str, dict[str, UUID]]", self.scope["url_route"]
        )
        self.lot_id = route_data["kwargs"]["lot_id"]
        scope_user = cast("User | None", self.scope.get("user"))
        ticket_valid = bool(self.scope.get("ws_ticket_valid"))
        if (
            scope_user is not None
            and scope_user.is_authenticated
            and not ticket_valid
        ):
            scope_user = None
        user_id = (
            scope_user.pk
            if scope_user is not None and scope_user.is_authenticated
            else None
        )
        snapshot = await _lot_snapshot(self.lot_id, user_id)
        if snapshot is None:
            await self.close(code=4404)
            return
        await self.channel_layer.group_add(
            f"lot_{self.lot_id}", self.channel_name
        )
        await self.accept()
        await self.send_json(snapshot)
        self.expiry_task: asyncio.Task[None] | None = None
        if ticket_valid and user_id is not None:
            self.expiry_task = asyncio.create_task(self._expire_connection())

    async def disconnect(self, close_code: int) -> None:
        del close_code
        task = getattr(self, "expiry_task", None)
        if task is not None:
            task.cancel()
        lot_id = getattr(self, "lot_id", None)
        if lot_id is not None:
            await self.channel_layer.group_discard(
                f"lot_{lot_id}", self.channel_name
            )

    async def lot_event(
        self, event: dict[str, str | int | dict[str, EventValue]]
    ) -> None:
        await self.send_json(
            {
                "event": event["event_name"],
                "state_version": event["state_version"],
                **cast("dict[str, EventValue]", event["payload"]),
            }
        )

    async def _expire_connection(self) -> None:
        await asyncio.sleep(settings.WS_CONNECTION_MAX_AGE_SECONDS)
        await self.close(code=4401)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """Caixa de eventos para o usuário autenticado por ticket."""

    async def connect(self) -> None:
        scope_user = cast("User | None", self.scope.get("user"))
        ticket_valid = bool(self.scope.get("ws_ticket_valid"))
        if (
            scope_user is None
            or not scope_user.is_authenticated
            or not ticket_valid
        ):
            await self.close(code=4401)
            return
        self.user_group = f"user_{scope_user.pk}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()
        self.expiry_task = asyncio.create_task(self._expire_connection())

    async def disconnect(self, close_code: int) -> None:
        del close_code
        task = getattr(self, "expiry_task", None)
        if task is not None:
            task.cancel()
        group = getattr(self, "user_group", None)
        if group is not None:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def user_event(
        self, event: dict[str, str | dict[str, EventValue]]
    ) -> None:
        await self.send_json(
            {
                "event": event["event_name"],
                **cast("dict[str, EventValue]", event["payload"]),
            }
        )

    async def _expire_connection(self) -> None:
        await asyncio.sleep(settings.WS_CONNECTION_MAX_AGE_SECONDS)
        await self.close(code=4401)
