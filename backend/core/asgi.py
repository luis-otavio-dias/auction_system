"""Roteamento ASGI HTTP/WebSocket e ciclo de vida do ticker."""

from __future__ import annotations

import asyncio
import os
from contextlib import suppress
from importlib import import_module
from logging import getLogger
from typing import TYPE_CHECKING, Protocol, cast

from asgiref.sync import sync_to_async
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
from django.core.asgi import get_asgi_application
from django.core.cache import cache

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from asgiref.typing import (
        ASGI3Application,
        ASGIReceiveCallable,
        ASGISendCallable,
        Scope,
    )
    from django.urls.resolvers import URLPattern

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django_application = get_asgi_application()
logger = getLogger(__name__)


class RoutingModule(Protocol):
    """Contrato tipado do módulo de rotas WebSocket."""

    websocket_urlpatterns: list[URLPattern]


class TicketMiddleware(Protocol):
    """Aplicação ASGI de validação de tickets."""

    def __init__(self, app: ASGI3Application) -> None: ...

    def __call__(
        self,
        scope: Scope,
        receive: ASGIReceiveCallable,
        send: ASGISendCallable,
    ) -> Awaitable[None]: ...


class WsAuthModule(Protocol):
    """Export tipado do middleware carregado após o setup Django."""

    WsTicketMiddleware: type[TicketMiddleware]


class TickerModule(Protocol):
    """Módulo que executa uma rodada síncrona do ticker."""

    def tick(self) -> int: ...


def build_websocket_application() -> ASGI3Application:
    """Monta o WebSocket lendo as origens permitidas na chamada.

    A validação usa apenas ``WS_ALLOWED_ORIGINS``. Não usamos
    ``AllowedHostsOriginValidator``: ``ALLOWED_HOSTS`` descreve o host da API,
    enquanto o navegador envia o host do frontend no cabeçalho ``Origin``.
    Em deploys com frontend e API em domínios distintos, como Vercel e
    Northflank, aquele validador recusaria uma origem explicitamente liberada
    em ``WS_ALLOWED_ORIGINS`` e o handshake terminaria em 403.
    """
    routes = cast(
        "RoutingModule", import_module("auctions.routing")
    ).websocket_urlpatterns
    middleware_module = cast("WsAuthModule", import_module("auctions.ws_auth"))
    return OriginValidator(
        middleware_module.WsTicketMiddleware(URLRouter(routes)),
        settings.WS_ALLOWED_ORIGINS,
    )


def build_application() -> ASGI3Application:
    """Monta o roteador ASGI HTTP/WebSocket."""
    protocol_router = ProtocolTypeRouter(
        {
            "http": django_application,
            "websocket": build_websocket_application(),
        }
    )
    return cast("ASGI3Application", protocol_router)


protocol_application = build_application()
ticker = cast("TickerModule", import_module("core.settlement_ticker"))


async def _settlement_ticker() -> None:
    while True:
        try:
            await sync_to_async(ticker.tick, thread_sensitive=True)()
        except Exception:
            logger.exception("Falha na rodada do ticker de liquidação")
            cache.set("settlement:last_run_at", "error", timeout=None)
        await asyncio.sleep(settings.SETTLEMENT_INTERVAL_SECONDS)


async def _lifespan(
    receive: ASGIReceiveCallable,
    send: ASGISendCallable,
) -> None:
    startup = await receive()
    if startup["type"] != "lifespan.startup":
        return
    task: asyncio.Task[None] | None = None
    if settings.ENABLE_SETTLEMENT_TICKER:
        task = asyncio.create_task(
            _settlement_ticker(), name="settlement-ticker"
        )
    await send({"type": "lifespan.startup.complete"})
    shutdown = await receive()
    if shutdown["type"] == "lifespan.shutdown" and task is not None:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    await send({"type": "lifespan.shutdown.complete"})


async def application(
    scope: Scope,
    receive: ASGIReceiveCallable,
    send: ASGISendCallable,
) -> None:
    """Despacha tráfego HTTP/WebSocket e ciclo de vida do ticker."""
    if scope["type"] == "lifespan":
        await _lifespan(receive, send)
        return
    await protocol_application(scope, receive, send)
