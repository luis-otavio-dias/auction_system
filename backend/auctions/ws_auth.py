"""Autenticação de WebSocket por ticket temporário assinado."""

from __future__ import annotations

from typing import TypedDict, cast
from urllib.parse import parse_qs

from asgiref.typing import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGISendCallable,
    Scope,
    WebSocketScope,
)
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

from users.models import User


class TicketPayload(TypedDict):
    """Campos assinados do ticket de WebSocket."""

    purpose: str
    user_id: str


class AuthenticatedWebSocketScope(WebSocketScope):
    """Extensão da scope com os dados validados pelo middleware."""

    user: User | AnonymousUser
    ws_ticket_valid: bool


@database_sync_to_async
def _user_by_id(user_id: str) -> User | AnonymousUser:
    user = User.objects.filter(pk=user_id, is_active=True).first()
    return user if user is not None else AnonymousUser()


class WsTicketMiddleware:
    """Valida ticket e associa o usuário à conexão WebSocket."""

    def __init__(self, app: ASGI3Application) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> None:
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return
        params = parse_qs(scope["query_string"].decode())
        tickets = params.get("ticket", [])
        user: User | AnonymousUser = AnonymousUser()
        valid = False
        if tickets:
            signer = TimestampSigner(salt="auction-ws-ticket")
            try:
                raw_payload = signer.unsign_object(
                    tickets[0], max_age=settings.WS_TICKET_MAX_AGE_SECONDS
                )
            except BadSignature, SignatureExpired:
                raw_payload = None
            if isinstance(raw_payload, dict):
                payload = cast("TicketPayload", raw_payload)
                if payload.get("purpose") == "ws" and isinstance(
                    payload.get("user_id"), str
                ):
                    loaded_user = await _user_by_id(payload["user_id"])
                    if loaded_user.is_authenticated:
                        user = loaded_user
                        valid = True
        authenticated_scope = cast("AuthenticatedWebSocketScope", dict(scope))
        authenticated_scope["user"] = user
        authenticated_scope["ws_ticket_valid"] = valid
        await self.app(authenticated_scope, receive, send)
