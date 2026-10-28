"""Publica eventos WebSocket best-effort após commit."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, TypedDict

from asgiref.sync import async_to_sync
from channels.exceptions import InvalidChannelLayerError
from channels.layers import get_channel_layer

if TYPE_CHECKING:
    from uuid import UUID

    from channels.layers import BaseChannelLayer

logger = logging.getLogger(__name__)
type EventValue = str | int | bool | None


class LotEvent(TypedDict):
    """Formato mínimo encaminhado a uma sala de lote."""

    type: str
    event_name: str
    state_version: int
    payload: dict[str, EventValue]


class UserEvent(TypedDict):
    """Formato mínimo encaminhado a uma caixa pessoal."""

    type: str
    event_name: str
    payload: dict[str, EventValue]


def _channel_layer() -> BaseChannelLayer | None:
    return get_channel_layer()


def publish_lot_event(
    lot_id: UUID,
    event_name: str,
    state_version: int,
    payload: dict[str, EventValue],
) -> None:
    """Envia evento ao grupo do lote sem deixar falhas escaparem."""
    try:
        layer = _channel_layer()
    except InvalidChannelLayerError, RuntimeError:
        logger.exception(
            "Channel layer indisponível para evento %s", event_name
        )
        return
    if layer is None:
        return
    message: LotEvent = {
        "type": "lot.event",
        "event_name": event_name,
        "state_version": state_version,
        "payload": payload,
    }
    try:
        async_to_sync(layer.group_send)(f"lot_{lot_id}", message)
    except Exception:
        logger.exception(
            "Falha ao publicar evento %s para lote %s", event_name, lot_id
        )


def publish_user_event(
    user_id: UUID,
    event_name: str,
    payload: dict[str, EventValue],
) -> None:
    """Envia notificação pessoal sem propagar falha de canal."""
    try:
        layer = _channel_layer()
    except InvalidChannelLayerError, RuntimeError:
        logger.exception(
            "Channel layer indisponível para evento %s", event_name
        )
        return
    if layer is None:
        return
    message: UserEvent = {
        "type": "user.event",
        "event_name": event_name,
        "payload": payload,
    }
    try:
        async_to_sync(layer.group_send)(f"user_{user_id}", message)
    except Exception:
        logger.exception(
            "Falha ao publicar evento %s para usuário", event_name
        )
