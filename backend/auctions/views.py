"""Views HTTP do catálogo e dos lotes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from auctions.models import Bid, Lot, Receipt
from auctions.permissions import IsBidder, IsSeller
from auctions.selectors import filter_lots, get_public_lot
from auctions.serializers import (
    BidCreateSerializer,
    BidSerializer,
    CatalogItemSerializer,
    CatalogSearchQuerySerializer,
    LotCancelSerializer,
    LotCreateSerializer,
    LotDetailSerializer,
    LotFilterSerializer,
    LotListSerializer,
    ReceiptSerializer,
)
from auctions.services.audit import verify_lot, verify_receipt
from auctions.services.bidding import (
    BidError,
    InsufficientFundsBidError,
    place_bid_result,
)
from auctions.services.catalog import (
    CatalogItemNotFoundError,
    CatalogUnavailableError,
    get_catalog_item,
    search_catalog,
)
from auctions.services.lots import LotError, LotNotFoundError, cancel_lot
from auctions.services.settlement import settle_if_due

if TYPE_CHECKING:
    from uuid import UUID

    from rest_framework.permissions import BasePermission
    from rest_framework.request import Request

    from users.models import User


def _error_response(*, code: str, detail: str, status_code: int) -> Response:
    return Response(
        {"code": code, "detail": detail},
        status=status_code,
    )


class CatalogSearchView(APIView):
    """Busca itens no catálogo externo com fallback para o cache local."""

    permission_classes = (IsSeller,)

    def get(self, request: Request) -> Response:
        query = CatalogSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        term = str(query.validated_data["q"])
        limit = int(query.validated_data["limit"])
        try:
            result = search_catalog(term, limit)
        except CatalogUnavailableError as exc:
            return _error_response(
                code=exc.code,
                detail=exc.detail,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        serializer = CatalogItemSerializer(
            result.items,
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "count": len(result.items),
                "from_cache": result.from_cache,
                "degraded": result.degraded,
                "results": serializer.data,
            },
        )


class CatalogItemDetailView(APIView):
    """Detalhe de um item já persistido no catálogo local."""

    permission_classes = (IsSeller,)

    def get(self, request: Request, item_id: UUID) -> Response:
        try:
            item = get_catalog_item(item_id)
        except CatalogItemNotFoundError as exc:
            return _error_response(
                code=exc.code,
                detail=exc.detail,
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            CatalogItemSerializer(
                item,
                context={"request": request},
            ).data,
        )


class LotListView(APIView):
    """Vitrine paginada de lotes e criação de novos lotes."""

    def get_permissions(self) -> list[BasePermission]:
        if self.request.method == "POST":
            return [IsSeller()]
        return [AllowAny()]

    def get(self, request: Request) -> Response:
        filters = LotFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        lots = filter_lots(
            tab=str(filters.validated_data["tab"]),
            q=str(filters.validated_data["q"]),
            category=str(filters.validated_data["category"]),
            sort=str(filters.validated_data["sort"]),
        )
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(lots, request, view=self)
        context = {"request": request}
        if page is None:
            serializer = LotListSerializer(lots, many=True, context=context)
            return Response(serializer.data)
        serializer = LotListSerializer(page, many=True, context=context)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        serializer = LotCreateSerializer(
            data=request.data,
            context={"seller": request.user},
        )
        serializer.is_valid(raise_exception=True)
        try:
            lot = cast("Lot", serializer.save())
        except LotError as exc:
            return _error_response(
                code=exc.code,
                detail=exc.detail,
                status_code=exc.status_code,
            )
        detail = LotDetailSerializer(
            lot,
            context={"request": request, "now": timezone.now()},
        )
        return Response(detail.data, status=status.HTTP_201_CREATED)


class LotDetailView(APIView):
    """Detalhe público de um lote, incluindo cancelados."""

    permission_classes = (AllowAny,)

    def get(self, request: Request, lot_id: UUID) -> Response:
        lot = get_public_lot(lot_id)
        if lot is None:
            error = LotNotFoundError()
            return _error_response(
                code=error.code,
                detail=error.detail,
                status_code=error.status_code,
            )
        settle_if_due(lot)
        lot = get_public_lot(lot_id)
        if lot is None:
            return _error_response(
                code="LOT_NOT_FOUND",
                detail="Lote não encontrado.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        detail = LotDetailSerializer(
            lot,
            context={"request": request, "now": timezone.now()},
        )
        return Response(detail.data)


class LotBidsView(APIView):
    """Cria lances autenticados e lista histórico público."""

    permission_classes = (AllowAny,)

    def get(self, request: Request, lot_id: UUID) -> Response:
        if not Lot.objects.filter(pk=lot_id).exists():
            return _error_response(
                code="LOT_NOT_FOUND",
                detail="Lote não encontrado.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        bids = Bid.objects.filter(lot_id=lot_id).select_related("bidder")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(bids, request, view=self)
        rows = page if page is not None else bids
        data = BidSerializer(
            rows, many=True, context={"request": request}
        ).data
        return (
            paginator.get_paginated_response(data)
            if page is not None
            else Response(data)
        )

    def post(self, request: Request, lot_id: UUID) -> Response:
        if not request.user.is_authenticated:
            return _error_response(
                code="FORBIDDEN_ROLE",
                detail="Autenticação necessária.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = BidCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            placement = place_bid_result(
                lot_id=lot_id,
                bidder=cast("User", request.user),
                amount=serializer.validated_data["amount"],
                client_bid_id=serializer.validated_data.get("client_bid_id"),
            )
        except BidError as exc:
            error_body = {"code": exc.code, "detail": str(exc)}
            if isinstance(exc, InsufficientFundsBidError):
                error_body["available"] = f"{exc.available:.2f}"
                error_body["minimum_bid"] = f"{exc.minimum_bid:.2f}"
            return Response(
                error_body,
                status=exc.status_code,
            )
        response = Response(
            BidSerializer(placement.bid, context={"request": request}).data,
            status=(
                status.HTTP_200_OK
                if placement.replayed
                else status.HTTP_201_CREATED
            ),
        )
        if placement.replayed:
            response["Idempotent-Replayed"] = "true"
        return response


class MyBidsView(APIView):
    """Lista os lances do licitante autenticado."""

    permission_classes = (IsBidder,)

    def get(self, request: Request) -> Response:
        bids = Bid.objects.filter(
            bidder=cast("User", request.user)
        ).select_related("lot")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(bids, request, view=self)
        rows = page if page is not None else bids
        data = BidSerializer(
            rows, many=True, context={"request": request}
        ).data
        return (
            paginator.get_paginated_response(data)
            if page is not None
            else Response(data)
        )


class SellerLotsView(APIView):
    """Lista lotes pertencentes ao leiloeiro autenticado."""

    permission_classes = (IsSeller,)

    def get(self, request: Request) -> Response:
        seller = cast("User", request.user)
        due_lots = Lot.objects.filter(
            seller=seller,
            settled_at__isnull=True,
            cancelled_at__isnull=True,
            settlement_error="",
            ends_at__lte=timezone.now(),
        )
        for due_lot in due_lots.iterator():
            settle_if_due(due_lot)
        lots = Lot.objects.filter(seller=seller).order_by("-created_at")
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(lots, request, view=self)
        rows = page if page is not None else lots
        data = LotListSerializer(
            rows,
            many=True,
            context={"request": request},
        ).data
        return (
            paginator.get_paginated_response(data)
            if page is not None
            else Response(data)
        )


class SellerSummaryView(APIView):
    """Resume valores recebidos e lotes bloqueados."""

    permission_classes = (IsSeller,)

    def get(self, request: Request) -> Response:
        seller = cast("User", request.user)
        due_lots = Lot.objects.filter(
            seller=seller,
            settled_at__isnull=True,
            cancelled_at__isnull=True,
            settlement_error="",
            ends_at__lte=timezone.now(),
        )
        for due_lot in due_lots.iterator():
            settle_if_due(due_lot)
        lots = Lot.objects.filter(seller=seller)
        total = (
            lots.filter(settled_at__isnull=False).aggregate(
                value=Sum("final_price")
            )["value"]
            or 0
        )
        results_by_lot = [
            {
                "lot_id": str(lot.pk),
                "code": lot.code,
                "title": lot.title,
                "final_price": f"{lot.final_price:.2f}"
                if lot.final_price is not None
                else None,
                "winner_alias": lot.winner.public_alias,
                "settled_at": lot.settled_at.isoformat()
                if lot.settled_at
                else None,
            }
            for lot in lots.filter(
                settled_at__isnull=False, winner__isnull=False
            ).select_related("winner")
            if lot.winner is not None
        ]
        unsold = [
            {
                "lot_id": str(lot.pk),
                "code": lot.code,
                "title": lot.title,
                "settled_at": lot.settled_at.isoformat()
                if lot.settled_at
                else None,
            }
            for lot in lots.filter(settled_at__isnull=False, bids_count=0)
        ]
        blocked = [
            {
                "lot_id": str(lot.pk),
                "code": lot.code,
                "title": lot.title,
                "settlement_error": lot.settlement_error,
            }
            for lot in lots.exclude(settlement_error="")
        ]
        return Response(
            {
                "total_received": f"{total:.2f}",
                "settled_count": lots.filter(settled_at__isnull=False).count(),
                "unsold_count": lots.filter(
                    settled_at__isnull=False, bids_count=0
                ).count(),
                "results_by_lot": results_by_lot,
                "unsold_lots": unsold,
                "blocked_lots": blocked,
            }
        )


class MyWinsView(APIView):
    """Lista arremates e comprovantes do usuário autenticado."""

    permission_classes = (IsBidder,)

    def get(self, request: Request) -> Response:
        due_lots = Lot.objects.filter(
            current_winner=cast("User", request.user),
            settled_at__isnull=True,
            cancelled_at__isnull=True,
            settlement_error="",
            ends_at__lte=timezone.now(),
        )
        for due_lot in due_lots.iterator():
            settle_if_due(due_lot)
        lots = (
            Lot.objects.filter(winner=cast("User", request.user))
            .select_related("receipt")
            .order_by("-settled_at")
        )
        results = [
            {
                "lot_code": lot.code,
                "title": lot.title,
                "final_price": f"{lot.final_price:.2f}"
                if lot.final_price is not None
                else None,
                "settled_at": lot.settled_at.isoformat()
                if lot.settled_at
                else None,
                "receipt_token": str(lot.receipt.token),
                "issued_at": lot.receipt.issued_at.isoformat(),
                "share_url": (
                    f"{settings.FRONTEND_URL.rstrip('/')}/comprovantes/"
                    f"{lot.receipt.token}"
                ),
            }
            for lot in lots
            if hasattr(lot, "receipt")
        ]
        return Response(results)


class ReceiptDetailView(APIView):
    """Entrega snapshot público do comprovante."""

    permission_classes = (AllowAny,)

    def get(self, request: Request, token: UUID) -> Response:
        receipt = Receipt.objects.filter(token=token).first()
        if receipt is None:
            return _error_response(
                code="RECEIPT_NOT_FOUND",
                detail="Comprovante não encontrado.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            ReceiptSerializer(
                receipt,
                context={"request": request},
            ).data,
        )


class LotAuditView(APIView):
    """Retorna o histórico e a verificação pública da cadeia."""

    permission_classes = (AllowAny,)

    def get(self, _request: Request, lot_id: UUID) -> Response:
        lot = Lot.objects.filter(pk=lot_id).first()
        if lot is None:
            return _error_response(
                code="LOT_NOT_FOUND",
                detail="Lote não encontrado.",
                status_code=404,
            )
        settle_if_due(lot)
        lot.refresh_from_db()
        return Response(verify_lot(lot))


class ReceiptVerifyView(APIView):
    """Verifica HMAC do comprovante e head congelado."""

    permission_classes = (AllowAny,)

    def get(self, _request: Request, token: UUID) -> Response:
        receipt = (
            Receipt.objects.filter(token=token).select_related("lot").first()
        )
        if receipt is None:
            return _error_response(
                code="RECEIPT_NOT_FOUND",
                detail="Comprovante não encontrado.",
                status_code=404,
            )
        return Response(verify_receipt(receipt))


class LotCancelView(APIView):
    """Cancelamento de lote pelo leiloeiro dono, antes de qualquer lance."""

    permission_classes = (IsSeller,)

    def post(self, request: Request, lot_id: UUID) -> Response:
        serializer = LotCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        seller = cast("User", request.user)
        try:
            lot = cancel_lot(
                lot_id=lot_id,
                seller=seller,
                reason=str(serializer.validated_data["reason"]),
            )
        except LotError as exc:
            return _error_response(
                code=exc.code,
                detail=exc.detail,
                status_code=exc.status_code,
            )
        detail = LotDetailSerializer(
            lot,
            context={"request": request, "now": timezone.now()},
        )
        return Response(detail.data)
