"""Serviços de domínio dos lotes."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, NotRequired, TypedDict, Unpack

from django.db import transaction
from django.utils import timezone

from auctions.events import publish_lot_event
from auctions.models import Lot
from auctions.services import images

if TYPE_CHECKING:
    from datetime import datetime
    from decimal import Decimal
    from uuid import UUID

    from auctions.models import CatalogItem
    from users.models import User


def cache_remote_image(image_url: str, external_id: str) -> str | None:
    """Adapta o download de imagem para permitir substituição em testes."""
    return images.cache_remote_image(image_url, external_id)


class LotError(Exception):
    """Erro base das operações de lote."""

    code: str = "LOT_ERROR"
    detail: str = "Não foi possível concluir a operação do lote."
    status_code: int = 409

    def __init__(self) -> None:
        super().__init__(self.detail)


class LotNotFoundError(LotError):
    """Lote inexistente."""

    code = "LOT_NOT_FOUND"
    detail = "Lote não encontrado."
    status_code = 404


class LotNotOwnedError(LotError):
    """Leiloeiro tentou agir sobre lote de terceiro."""

    code = "LOT_NOT_OWNED"
    detail = "Você não é o leiloeiro responsável por este lote."
    status_code = 403


class ForbiddenRoleError(LotError):
    """Usuário sem papel de leiloeiro."""

    code = "FORBIDDEN_ROLE"
    detail = "Apenas leiloeiros podem realizar esta operação."
    status_code = 403


class LotHasBidsError(LotError):
    """Cancelamento bloqueado por lances existentes."""

    code = "LOT_HAS_BIDS"
    detail = "Lotes que já receberam lances não podem ser cancelados."
    status_code = 409


class LotEndedError(LotError):
    """Cancelamento bloqueado após o encerramento."""

    code = "LOT_ENDED"
    detail = "O lote já foi encerrado e não pode ser cancelado."
    status_code = 409


class LotAlreadyCancelledError(LotError):
    """Cancelamento repetido."""

    code = "LOT_CANCELLED"
    detail = "O lote já está cancelado."
    status_code = 409


class InvalidLotScheduleError(LotError):
    """Datas de lote inconsistentes ou ingênuas."""

    code = "INVALID_LOT_SCHEDULE"
    detail = (
        "As datas do lote são inválidas: use datas com fuso horário, "
        "com início anterior ao fim e encerramento no futuro."
    )
    status_code = 422


class InvalidLotAmountError(LotError):
    """Valores de lote inválidos."""

    code = "INVALID_LOT_AMOUNT"
    detail = "Os valores do lote devem ser positivos e finitos."
    status_code = 422


class CreateLotParams(TypedDict):
    """Parâmetros nomeados de criação de lote.

    O TypedDict mantém o contrato de chamada por palavra-chave sem exceder o
    limite de argumentos da regra PLR0913 do ruff.
    """

    seller: User
    catalog_item: CatalogItem
    starts_at: datetime
    ends_at: datetime
    starting_bid: Decimal
    min_increment: Decimal
    cache_image: NotRequired[bool]


def _validate_amount(amount: Decimal) -> None:
    if not amount.is_finite() or amount <= 0:
        raise InvalidLotAmountError


def _validate_schedule(
    *,
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
) -> None:
    if not timezone.is_aware(starts_at) or not timezone.is_aware(ends_at):
        raise InvalidLotScheduleError
    if starts_at >= ends_at or ends_at <= now:
        raise InvalidLotScheduleError


def create_lot(**params: Unpack[CreateLotParams]) -> Lot:
    """Cria um lote a partir do snapshot de um item do catálogo."""
    seller = params["seller"]
    catalog_item = params["catalog_item"]
    starts_at = params["starts_at"]
    ends_at = params["ends_at"]
    starting_bid = params["starting_bid"]
    min_increment = params["min_increment"]

    if not seller.is_seller:
        raise ForbiddenRoleError

    _validate_amount(starting_bid)
    _validate_amount(min_increment)
    _validate_schedule(
        starts_at=starts_at,
        ends_at=ends_at,
        now=timezone.now(),
    )

    cached_image = (
        cache_remote_image(catalog_item.image_url, catalog_item.external_id)
        if params.get("cache_image", True)
        else None
    )
    image_cached = cached_image is not None
    image_url = (
        cached_image if cached_image is not None else catalog_item.image_url
    )

    with transaction.atomic():
        return Lot.objects.create(
            seller=seller,
            catalog_item=catalog_item,
            title=catalog_item.title,
            description=catalog_item.description,
            image_url=image_url,
            image_remote_url=catalog_item.image_url,
            image_cached=image_cached,
            source=catalog_item.source,
            external_id=catalog_item.external_id,
            source_url=catalog_item.source_url,
            category=catalog_item.category,
            attributes=catalog_item.attributes,
            starting_bid=starting_bid,
            min_increment=min_increment,
            current_bid=None,
            current_winner=None,
            starts_at=starts_at,
            ends_at=ends_at,
            original_ends_at=ends_at,
            state_version=1,
        )


def cancel_lot(*, lot_id: UUID, seller: User, reason: str = "") -> Lot:
    """Cancela um lote sem lances, antes do encerramento."""
    if not seller.is_seller:
        raise ForbiddenRoleError

    with transaction.atomic():
        lot = Lot.objects.select_for_update().filter(pk=lot_id).first()
        if lot is None:
            raise LotNotFoundError

        now = timezone.now()

        if lot.seller_id != seller.pk:
            raise LotNotOwnedError
        if lot.cancelled_at is not None:
            raise LotAlreadyCancelledError
        if now >= lot.ends_at:
            raise LotEndedError
        if lot.bids_count > 0:
            raise LotHasBidsError

        lot.cancelled_at = now
        lot.cancelled_by = seller
        lot.cancel_reason = reason
        lot.state_version += 1
        lot.save(
            update_fields=(
                "cancelled_at",
                "cancelled_by",
                "cancel_reason",
                "state_version",
                "updated_at",
            ),
        )
        transaction.on_commit(
            partial(
                publish_lot_event,
                lot.pk,
                "lot.cancelled",
                lot.state_version,
                {"reason": reason},
            )
        )

    return lot
