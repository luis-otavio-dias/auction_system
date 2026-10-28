"""Views de autenticação JWT baseada em cookies."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, cast

from django.conf import settings
from django.core.signing import TimestampSigner
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from users.serializers import RegisterSerializer, UserMeSerializer

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework_simplejwt.tokens import Token

    from users.models import User

logger = logging.getLogger(__name__)

CookieSameSite = Literal["Lax", "Strict", "None", False]


def _cookie_samesite() -> CookieSameSite | None:
    return cast("CookieSameSite | None", settings.AUTH_COOKIE_SAMESITE)


def _set_access_cookie(response: Response, access: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_ACCESS_NAME,
        value=access,
        max_age=settings.AUTH_COOKIE_ACCESS_MAX_AGE,
        path=settings.AUTH_COOKIE_ACCESS_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=settings.AUTH_COOKIE_HTTP_ONLY,
        samesite=_cookie_samesite(),
    )


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    response.set_cookie(
        key=settings.AUTH_COOKIE_REFRESH_NAME,
        value=refresh,
        max_age=settings.AUTH_COOKIE_REFRESH_MAX_AGE,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=settings.AUTH_COOKIE_HTTP_ONLY,
        samesite=_cookie_samesite(),
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_COOKIE_ACCESS_NAME,
        path=settings.AUTH_COOKIE_ACCESS_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        samesite=_cookie_samesite(),
    )
    response.delete_cookie(
        key=settings.AUTH_COOKIE_REFRESH_NAME,
        path=settings.AUTH_COOKIE_REFRESH_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
        samesite=_cookie_samesite(),
    )


class CookieTokenObtainPairView(TokenObtainPairView):
    """Login que entrega access e refresh em cookies HttpOnly."""

    def post(
        self,
        request: Request,
        *_args: str,
        **_kwargs: str,
    ) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        access = str(serializer.validated_data["access"])
        refresh = str(serializer.validated_data["refresh"])

        response = Response(
            {"detail": "Login realizado com sucesso."},
            status=status.HTTP_200_OK,
        )
        _set_access_cookie(response, access)
        _set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Renova o access token usando o refresh armazenado em cookie."""

    def post(
        self,
        request: Request,
        *_args: str,
        **_kwargs: str,
    ) -> Response:
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if refresh_token is None:
            return Response(
                {"detail": "Refresh token não encontrado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(data={"refresh": refresh_token})
        try:
            serializer.is_valid(raise_exception=True)
        except InvalidToken, TokenError:
            response = Response(
                {"detail": "Refresh token inválido ou expirado."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            _clear_auth_cookies(response)
            return response

        response = Response(
            {"detail": "Token renovado com sucesso."},
            status=status.HTTP_200_OK,
        )
        _set_access_cookie(response, str(serializer.validated_data["access"]))

        rotated_refresh = serializer.validated_data.get("refresh")
        if rotated_refresh is not None:
            _set_refresh_cookie(response, str(rotated_refresh))

        return response


class CookieLogoutView(APIView):
    """Remove os cookies de autenticação."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        refresh_token = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH_NAME)
        if refresh_token is not None:
            try:
                RefreshToken(cast("Token", refresh_token)).blacklist()
            except TokenError:
                logger.info(
                    "Refresh token inválido ou já revogado durante logout.",
                )

        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_auth_cookies(response)
        return response


class MeView(APIView):
    """Retorna os dados privados do usuário autenticado."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user = cast("User", request.user)
        return Response(UserMeSerializer(user).data)


class RegisterView(APIView):
    """Cadastro público com papel explícito e alias opcional."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request: Request) -> Response:
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"detail": "Cadastro concluído."}, status=status.HTTP_201_CREATED
        )


class WsTicketView(APIView):
    """Emite ticket temporário assinado para autenticação WebSocket."""

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        signer = TimestampSigner(salt="auction-ws-ticket")
        ticket = signer.sign_object(
            {"purpose": "ws", "user_id": str(request.user.pk)}
        )
        return Response(
            {
                "ticket": ticket,
                "expires_in": settings.WS_TICKET_MAX_AGE_SECONDS,
            }
        )
