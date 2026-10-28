from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from rest_framework.request import Request


class HealthCheckView(APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        del request
        return Response({"status": "ok"})


class SettlementHealthView(APIView):
    """Estado local do ticker sem expor dados pessoais."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request: Request) -> Response:
        del request
        return Response(
            {
                "ticker_enabled": settings.ENABLE_SETTLEMENT_TICKER,
                "last_run_at": cache.get("settlement:last_run_at"),
                "last_success_at": cache.get("settlement:last_success_at"),
                "due_count": cache.get("settlement:due_count", 0),
                "blocked_count": cache.get("settlement:blocked_count", 0),
            }
        )
