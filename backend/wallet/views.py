"""Endpoints privados de carteira."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from wallet.models import Wallet, WalletTransaction
from wallet.permissions import IsBidder
from wallet.serializers import (
    DepositSerializer,
    WalletSerializer,
    WalletTransactionSerializer,
)
from wallet.services import (
    IdempotencyConflictError,
    InvalidAmountError,
    deposit,
)

if TYPE_CHECKING:
    from rest_framework.request import Request

    from users.models import User


class WalletView(APIView):
    """Lê a carteira do usuário autenticado."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        wallet = Wallet.objects.get(user=cast("User", request.user))
        return Response(WalletSerializer(wallet).data)


class WalletDepositView(APIView):
    """Permite depósitos simulados apenas para licitantes."""

    permission_classes = (IsBidder,)

    def post(self, request: Request) -> Response:
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        wallet = Wallet.objects.get(user=cast("User", request.user))
        try:
            result = deposit(
                wallet.pk,
                serializer.validated_data["amount"],
                serializer.validated_data.get("idempotency_key"),
                "Depósito simulado",
            )
        except IdempotencyConflictError as exc:
            return Response(
                {"code": "IDEMPOTENCY_KEY_REUSED", "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except InvalidAmountError as exc:
            return Response(
                {"code": "INVALID_AMOUNT", "detail": str(exc)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        wallet.refresh_from_db()
        response = Response(
            WalletSerializer(wallet).data,
            status=(
                status.HTTP_200_OK
                if result.replayed
                else status.HTTP_201_CREATED
            ),
        )
        if result.replayed:
            response["Idempotent-Replayed"] = "true"
        return response


class WalletTransactionsView(APIView):
    """Lista o extrato privado do usuário autenticado."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        wallet = Wallet.objects.get(user=cast("User", request.user))
        rows = WalletTransaction.objects.filter(wallet=wallet).order_by(
            "-created_at"
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        if page is None:
            return Response(WalletTransactionSerializer(rows, many=True).data)
        return paginator.get_paginated_response(
            WalletTransactionSerializer(page, many=True).data
        )
