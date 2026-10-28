"""Autenticação JWT baseada em cookie HttpOnly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from rest_framework import HTTP_HEADER_ENCODING
from rest_framework_simplejwt.authentication import (
    AUTH_HEADER_TYPES,
    JWTAuthentication,
)

if TYPE_CHECKING:
    from rest_framework.request import Request


class CookieJWTAuthentication(JWTAuthentication):
    """Lê o access token do cookie e mantém fallback para o header Bearer.

    O cookie é HttpOnly, então o JavaScript não consegue lê-lo. O fallback
    para ``Authorization: Bearer`` continua disponível para ferramentas e
    clientes de API.

    Segurança: o cookie usa ``SameSite`` configurável. Em deploy cross-site,
    use ``SameSite=None`` com ``Secure=True`` e adicione proteção CSRF
    explícita aos endpoints que alteram estado.
    """

    def get_header(self, request: Request) -> bytes:
        """Monta o header Bearer a partir do cookie de acesso."""
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS_NAME)
        if raw_token is not None:
            return f"{AUTH_HEADER_TYPES[0]} {raw_token}".encode(
                HTTP_HEADER_ENCODING,
            )
        return super().get_header(request)
