"""Testes do model de lote e de suas invariantes no banco."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from auctions.models import Lot, generate_lot_code

if TYPE_CHECKING:
    from auctions.models import CatalogItem
    from users.models import User


pytestmark = pytest.mark.django_db


def create_second_lot(
    seller: User,
    catalog_item: CatalogItem,
    *,
    code: str | None = None,
) -> Lot:
    """Cria um lote válido e independente do fixture ``lot``."""
    now = timezone.now()
    ends_at = now + timedelta(hours=1)
    return Lot.objects.create(
        code=code or generate_lot_code(),
        seller=seller,
        catalog_item=catalog_item,
        title="Outro lote",
        description="Descrição do outro lote.",
        image_url=catalog_item.image_url,
        image_remote_url=catalog_item.image_url,
        source=catalog_item.source,
        external_id=catalog_item.external_id,
        source_url=catalog_item.source_url,
        category=catalog_item.category,
        attributes=catalog_item.attributes,
        starting_bid=Decimal("100.00"),
        min_increment=Decimal("10.00"),
        starts_at=now - timedelta(hours=1),
        ends_at=ends_at,
        original_ends_at=ends_at,
    )


def test_minimum_bid_without_bids_equals_starting_bid(lot: Lot) -> None:
    assert lot.current_bid is None
    assert lot.minimum_bid == lot.starting_bid


def test_minimum_bid_with_bids_adds_increment(lot: Lot) -> None:
    lot.current_bid = Decimal("1250.00")

    assert lot.minimum_bid == Decimal("1350.00")


def test_has_bids_tracks_bids_count(lot: Lot) -> None:
    assert not lot.has_bids

    lot.bids_count = 1

    assert lot.has_bids


def test_cancelled_flag_uses_cancelled_at(lot: Lot) -> None:
    assert not lot.is_cancelled

    lot.cancelled_at = timezone.now()

    assert lot.is_cancelled


def test_settled_flag_uses_settled_at(lot: Lot) -> None:
    assert not lot.is_settled

    lot.settled_at = timezone.now()

    assert lot.is_settled


def test_status_at_scheduled_before_start(lot: Lot) -> None:
    moment = lot.starts_at - timedelta(seconds=1)

    assert lot.status_at(moment) == Lot.Status.SCHEDULED


def test_status_at_live_between_dates(lot: Lot) -> None:
    assert lot.status_at(lot.starts_at) == Lot.Status.LIVE
    assert lot.status_at(lot.ends_at - timedelta(seconds=1)) == Lot.Status.LIVE


def test_status_at_ended_at_ends_at(lot: Lot) -> None:
    assert lot.status_at(lot.ends_at) == Lot.Status.ENDED
    assert lot.status_at(lot.ends_at + timedelta(hours=1)) == Lot.Status.ENDED


def test_status_at_cancelled_wins_over_other_states(lot: Lot) -> None:
    lot.cancelled_at = timezone.now()

    assert lot.status_at(lot.starts_at) == Lot.Status.CANCELLED
    assert (
        lot.status_at(lot.starts_at - timedelta(hours=1))
        == Lot.Status.CANCELLED
    )


def test_status_at_settled_is_ended(lot: Lot) -> None:
    lot.settled_at = timezone.now()

    assert lot.status_at(lot.starts_at) == Lot.Status.ENDED


def test_status_property_uses_current_time(lot: Lot) -> None:
    assert lot.status == Lot.Status.LIVE


def test_ends_at_must_be_after_starts_at(lot: Lot) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(ends_at=lot.starts_at)


def test_starting_bid_must_be_positive(lot: Lot) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(starting_bid=Decimal("0.00"))

    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(starting_bid=Decimal("-1.00"))


def test_min_increment_must_be_positive(lot: Lot) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(min_increment=Decimal("0.00"))

    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(min_increment=Decimal("-1.00"))


def test_current_bid_cannot_be_below_starting_bid(lot: Lot) -> None:
    below = lot.starting_bid - Decimal("0.01")

    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(current_bid=below)


def test_current_winner_requires_current_bid(
    lot: Lot,
    bidder: User,
) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(current_winner=bidder)


def test_state_version_must_be_at_least_one(lot: Lot) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        Lot.objects.filter(pk=lot.pk).update(state_version=0)


def test_lot_code_has_twelve_characters(lot: Lot) -> None:
    assert len(lot.code) == 12
    assert lot.code.startswith("L-")


def test_generated_codes_are_unique(
    seller: User,
    catalog_item: CatalogItem,
    lot: Lot,
) -> None:
    second = create_second_lot(seller, catalog_item)

    assert second.code != lot.code


def test_lot_code_is_unique_in_database(
    seller: User,
    catalog_item: CatalogItem,
    lot: Lot,
) -> None:
    with transaction.atomic(), pytest.raises(IntegrityError):
        create_second_lot(seller, catalog_item, code=lot.code)


def test_catalog_item_is_immutable_after_creation(
    catalog_item: CatalogItem,
) -> None:
    catalog_item.title = "Título alterado"

    with pytest.raises(ValueError, match="imutável"):
        catalog_item.save()


def test_catalog_item_snapshot_is_preserved_by_lot(
    lot: Lot,
    catalog_item: CatalogItem,
) -> None:
    assert lot.title == catalog_item.title
    assert lot.source == catalog_item.source
    assert lot.external_id == catalog_item.external_id
    assert lot.attributes == catalog_item.attributes
