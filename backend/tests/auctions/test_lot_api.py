"""Testes de API da vitrine, criação, detalhe e cancelamento de lotes."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from http import HTTPStatus
from typing import TYPE_CHECKING, TypedDict

import pytest
from django.utils import timezone

from auctions.models import Lot
from auctions.services.bidding import place_bid
from users.models import User
from wallet.models import Wallet

if TYPE_CHECKING:
    from typing import Unpack

    from django.test import Client

    from auctions.models import CatalogItem


pytestmark = pytest.mark.django_db

LOTS_URL = "/api/lots"


class LotOverrides(TypedDict, total=False):
    """Campos que os testes podem sobrescrever ao criar um lote."""

    title: str
    description: str
    category: str
    starts_at: datetime
    ends_at: datetime
    original_ends_at: datetime
    starting_bid: Decimal
    min_increment: Decimal
    current_bid: Decimal | None
    bids_count: int
    cancelled_at: datetime | None
    cancelled_by: User | None


def stub_cache_remote_image(
    _image_url: str,
    _external_id: str,
) -> str | None:
    """Impede que a criação de lote tente baixar imagens reais."""
    return None


@pytest.fixture(autouse=True)
def disable_remote_image_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "auctions.services.lots.cache_remote_image",
        stub_cache_remote_image,
    )


def create_lot_record(
    seller: User,
    catalog_item: CatalogItem,
    **overrides: Unpack[LotOverrides],
) -> Lot:
    """Cria um lote diretamente pelo ORM com padrões válidos."""
    now = timezone.now()
    ends_at = overrides.get("ends_at", now + timedelta(hours=1))
    starts_at = overrides.get("starts_at", now - timedelta(hours=1))
    return Lot.objects.create(
        seller=seller,
        catalog_item=catalog_item,
        title=overrides.get("title", catalog_item.title),
        description=overrides.get("description", catalog_item.description),
        image_url=catalog_item.image_url,
        image_remote_url=catalog_item.image_url,
        image_cached=False,
        source=catalog_item.source,
        external_id=catalog_item.external_id,
        source_url=catalog_item.source_url,
        category=overrides.get("category", catalog_item.category),
        attributes=catalog_item.attributes,
        starting_bid=overrides.get("starting_bid", Decimal("1000.00")),
        min_increment=overrides.get("min_increment", Decimal("100.00")),
        current_bid=overrides.get("current_bid"),
        starts_at=starts_at,
        ends_at=ends_at,
        original_ends_at=overrides.get("original_ends_at", ends_at),
        bids_count=overrides.get("bids_count", 0),
        cancelled_at=overrides.get("cancelled_at"),
        cancelled_by=overrides.get("cancelled_by"),
    )


def lot_payload(
    catalog_item: CatalogItem,
    starts_at: datetime,
    ends_at: datetime,
    *,
    starting_bid: str = "1000.00",
    min_increment: str = "100.00",
) -> dict[str, str]:
    return {
        "catalog_item_id": str(catalog_item.id),
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "starting_bid": starting_bid,
        "min_increment": min_increment,
    }


class LotListPayload(TypedDict):
    """Formato da resposta paginada da vitrine."""

    count: int
    next: str | None
    previous: str | None
    results: list[dict[str, str | int | None]]


def result_ids(response_payload: LotListPayload) -> list[str]:
    return [str(item["id"]) for item in response_payload["results"]]


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def test_create_lot_as_seller_copies_snapshot(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
    login,
) -> None:
    login(seller)
    now = timezone.now()
    starts_at = now - timedelta(minutes=5)
    ends_at = now + timedelta(hours=2)

    response = client.post(
        LOTS_URL,
        data=lot_payload(catalog_item, starts_at, ends_at),
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    payload = response.json()
    assert payload["title"] == catalog_item.title
    assert payload["description"] == catalog_item.description
    assert payload["image_url"] == catalog_item.image_url
    assert payload["source"] == catalog_item.source
    assert payload["external_id"] == catalog_item.external_id
    assert payload["source_url"] == catalog_item.source_url
    assert payload["category"] == catalog_item.category
    assert payload["attributes"] == catalog_item.attributes
    assert payload["status"] == "live"
    assert payload["starting_bid"] == "1000.00"
    assert payload["min_increment"] == "100.00"
    assert payload["current_bid"] is None
    assert payload["minimum_bid"] == "1000.00"
    assert payload["state_version"] == 1
    assert payload["bids_count"] == 0
    assert payload["original_ends_at"] == payload["ends_at"]
    assert payload["seller_alias"] == seller.public_alias
    assert len(payload["code"]) == 12

    lot = Lot.objects.get(pk=payload["id"])
    assert lot.seller_id == seller.id
    assert lot.current_winner_id is None
    assert lot.current_bid is None
    assert lot.state_version == 1
    assert lot.original_ends_at == lot.ends_at
    assert parse_timestamp(payload["ends_at"]) == lot.ends_at


def test_create_lot_rejects_bidder(
    client: Client,
    bidder: User,
    catalog_item: CatalogItem,
    login,
) -> None:
    login(bidder)
    now = timezone.now()

    response = client.post(
        LOTS_URL,
        data=lot_payload(
            catalog_item,
            now - timedelta(minutes=5),
            now + timedelta(hours=1),
        ),
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.FORBIDDEN


def test_create_lot_rejects_anonymous(
    client: Client,
    catalog_item: CatalogItem,
) -> None:
    now = timezone.now()

    response = client.post(
        LOTS_URL,
        data=lot_payload(
            catalog_item,
            now - timedelta(minutes=5),
            now + timedelta(hours=1),
        ),
        content_type="application/json",
    )

    assert response.status_code in {
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    }


def test_create_lot_ignores_foreign_seller_in_payload(
    client: Client,
    seller: User,
    other_seller: User,
    catalog_item: CatalogItem,
    login,
) -> None:
    login(seller)
    now = timezone.now()
    payload = lot_payload(
        catalog_item,
        now - timedelta(minutes=5),
        now + timedelta(hours=1),
    )
    payload["seller"] = str(other_seller.id)
    payload["seller_id"] = str(other_seller.id)

    response = client.post(
        LOTS_URL,
        data=payload,
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    lot = Lot.objects.get(pk=response.json()["id"])
    assert lot.seller_id == seller.id


def test_create_lot_rejects_starts_at_after_ends_at(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
    login,
) -> None:
    login(seller)
    now = timezone.now()

    response = client.post(
        LOTS_URL,
        data=lot_payload(
            catalog_item,
            now + timedelta(hours=2),
            now + timedelta(hours=1),
        ),
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Lot.objects.exists()


def test_create_lot_rejects_ends_at_in_the_past(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
    login,
) -> None:
    login(seller)
    now = timezone.now()

    response = client.post(
        LOTS_URL,
        data=lot_payload(
            catalog_item,
            now - timedelta(hours=2),
            now - timedelta(hours=1),
        ),
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert not Lot.objects.exists()


def test_create_lot_rejects_invalid_amounts(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
    login,
) -> None:
    login(seller)
    now = timezone.now()
    invalid_values = (
        ("starting_bid", "0.00"),
        ("starting_bid", "-1.00"),
        ("min_increment", "0.00"),
    )

    for field, value in invalid_values:
        payload = lot_payload(
            catalog_item,
            now - timedelta(minutes=5),
            now + timedelta(hours=1),
        )
        payload[field] = value

        response = client.post(
            LOTS_URL,
            data=payload,
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert field in response.json()

    assert not Lot.objects.exists()


def test_list_lots_is_public_and_excludes_cancelled(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    visible = create_lot_record(seller, catalog_item)
    cancelled = create_lot_record(
        seller,
        catalog_item,
        cancelled_at=timezone.now(),
        cancelled_by=seller,
    )

    response = client.get(LOTS_URL)

    assert response.status_code == HTTPStatus.OK
    ids = result_ids(response.json())
    assert str(visible.id) in ids
    assert str(cancelled.id) not in ids
    assert set(response.json()) >= {
        "count",
        "next",
        "previous",
        "results",
    }


def test_list_filters_by_tab(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    now = timezone.now()
    live = create_lot_record(seller, catalog_item)
    scheduled = create_lot_record(
        seller,
        catalog_item,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=2),
    )
    ended = create_lot_record(
        seller,
        catalog_item,
        starts_at=now - timedelta(hours=2),
        ends_at=now - timedelta(hours=1),
    )
    cancelled = create_lot_record(
        seller,
        catalog_item,
        cancelled_at=now,
        cancelled_by=seller,
    )

    live_ids = set(result_ids(client.get(f"{LOTS_URL}?tab=live").json()))
    scheduled_ids = set(
        result_ids(client.get(f"{LOTS_URL}?tab=scheduled").json()),
    )
    ended_ids = set(result_ids(client.get(f"{LOTS_URL}?tab=ended").json()))

    assert live_ids == {str(live.id)}
    assert scheduled_ids == {str(scheduled.id)}
    assert ended_ids == {str(ended.id)}
    assert str(cancelled.id) not in live_ids | scheduled_ids | ended_ids


def test_list_filters_by_category(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    target = create_lot_record(
        seller,
        catalog_item,
        category="Contemporary Art",
    )
    other = create_lot_record(
        seller,
        catalog_item,
        category="Impressionism",
    )

    response = client.get(f"{LOTS_URL}?category=contemporary art")

    assert response.status_code == HTTPStatus.OK
    assert result_ids(response.json()) == [str(target.id)]
    assert str(other.id) not in result_ids(response.json())


def test_list_searches_by_title_description_and_category(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    by_title = create_lot_record(
        seller,
        catalog_item,
        title="Starry Night",
        description="Obra de Alma Thomas.",
    )
    by_description = create_lot_record(
        seller,
        catalog_item,
        title="Outra obra",
        description="Óleo sobre tela.",
    )
    by_category = create_lot_record(
        seller,
        catalog_item,
        title="Sem título",
        category="Gravura",
    )
    unrelated = create_lot_record(
        seller,
        catalog_item,
        title="Water Lilies",
        description="Natureza morta.",
        category="Impressionism",
    )

    title_response = client.get(f"{LOTS_URL}?q=starry")
    assert result_ids(title_response.json()) == [str(by_title.id)]

    description_response = client.get(f"{LOTS_URL}?q=sobre tela")
    assert str(by_description.id) in result_ids(description_response.json())
    assert str(unrelated.id) not in result_ids(description_response.json())

    category_response = client.get(f"{LOTS_URL}?q=gravura")
    assert str(by_category.id) in result_ids(category_response.json())
    assert str(unrelated.id) not in result_ids(category_response.json())


def test_list_sorts_by_ending_soonest(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    now = timezone.now()
    late = create_lot_record(
        seller,
        catalog_item,
        ends_at=now + timedelta(hours=3),
    )
    early = create_lot_record(
        seller,
        catalog_item,
        ends_at=now + timedelta(hours=1),
    )
    middle = create_lot_record(
        seller,
        catalog_item,
        ends_at=now + timedelta(hours=2),
    )

    response = client.get(f"{LOTS_URL}?sort=ending")

    assert result_ids(response.json()) == [
        str(early.id),
        str(middle.id),
        str(late.id),
    ]


def test_list_sorts_by_effective_price(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    low = create_lot_record(
        seller,
        catalog_item,
        starting_bid=Decimal("500.00"),
    )
    high = create_lot_record(
        seller,
        catalog_item,
        starting_bid=Decimal("2000.00"),
    )
    bid = create_lot_record(
        seller,
        catalog_item,
        starting_bid=Decimal("1000.00"),
        current_bid=Decimal("1500.00"),
    )

    high_response = client.get(f"{LOTS_URL}?sort=price-high")
    assert result_ids(high_response.json()) == [
        str(high.id),
        str(bid.id),
        str(low.id),
    ]

    low_response = client.get(f"{LOTS_URL}?sort=price-low")
    assert result_ids(low_response.json()) == [
        str(low.id),
        str(bid.id),
        str(high.id),
    ]


def test_list_sorts_by_recent_creation(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    oldest = create_lot_record(seller, catalog_item, title="Antigo")
    middle = create_lot_record(seller, catalog_item, title="Meio")
    newest = create_lot_record(seller, catalog_item, title="Novo")
    base = timezone.now() - timedelta(days=1)
    for offset, lot in enumerate((oldest, middle, newest)):
        Lot.objects.filter(pk=lot.pk).update(
            created_at=base + timedelta(minutes=offset),
        )

    response = client.get(f"{LOTS_URL}?sort=recent")

    assert result_ids(response.json()) == [
        str(newest.id),
        str(middle.id),
        str(oldest.id),
    ]


def test_list_is_paginated(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    lots = [create_lot_record(seller, catalog_item) for _ in range(21)]

    first_page = client.get(LOTS_URL).json()

    assert first_page["count"] == 21
    assert first_page["next"] is not None
    assert first_page["previous"] is None
    assert len(first_page["results"]) == 20

    second_page = client.get(f"{LOTS_URL}?page=2").json()

    assert second_page["count"] == 21
    assert second_page["previous"] is not None
    assert len(result_ids(second_page)) == 1
    assert set(result_ids(second_page)) <= {str(lot.id) for lot in lots}


def test_public_detail_contains_contract_fields(
    client: Client,
    seller: User,
    lot: Lot,
) -> None:
    response = client.get(f"{LOTS_URL}/{lot.id}")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    expected_fields = {
        "id",
        "code",
        "status",
        "title",
        "description",
        "image_url",
        "source",
        "external_id",
        "source_url",
        "category",
        "attributes",
        "starting_bid",
        "min_increment",
        "current_bid",
        "minimum_bid",
        "starts_at",
        "ends_at",
        "original_ends_at",
        "extension_count",
        "bids_count",
        "state_version",
        "seller_alias",
        "my_position",
        "server_time",
    }

    assert expected_fields <= payload.keys()
    assert payload["id"] == str(lot.id)
    assert payload["code"] == lot.code
    assert payload["status"] == "live"
    assert payload["seller_alias"] == seller.public_alias
    assert payload["my_position"] is None
    assert payload["server_time"]
    assert parse_timestamp(payload["server_time"])
    assert payload["state_version"] == 1
    assert payload["current_bid"] is None
    assert payload["minimum_bid"] == "1000.00"
    assert payload["starting_bid"] == "1000.00"
    assert payload["min_increment"] == "100.00"
    assert "settlement_error" not in payload
    assert "settlement_checked_at" not in payload


def test_public_detail_minimum_bid_after_bid(
    client: Client,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    lot = create_lot_record(
        seller,
        catalog_item,
        current_bid=Decimal("1200.00"),
        bids_count=1,
    )

    response = client.get(f"{LOTS_URL}/{lot.id}")

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["current_bid"] == "1200.00"
    assert payload["minimum_bid"] == "1300.00"


def test_lot_detail_reports_authenticated_position_and_rank(
    client: Client, lot: Lot, bidder: User, login
) -> None:
    other = User.objects.create_user(
        email="position-other@example.com",
        password="test-password-123",
        role="BIDDER",
    )
    third = User.objects.create_user(
        email="position-third@example.com",
        password="test-password-123",
        role="BIDDER",
    )
    for user in (bidder, other, third):
        wallet = Wallet.objects.get(user=user)
        wallet.balance = Decimal("10000.00")
        wallet.save(update_fields=("balance",))
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    place_bid(lot_id=lot.pk, bidder=other, amount=Decimal("1100.00"))
    place_bid(lot_id=lot.pk, bidder=third, amount=Decimal("1200.00"))

    anonymous = client.get(f"{LOTS_URL}/{lot.pk}")
    assert anonymous.status_code == HTTPStatus.OK
    assert anonymous.json()["my_position"] is None

    login(bidder)
    response = client.get(f"{LOTS_URL}/{lot.pk}")
    assert response.status_code == HTTPStatus.OK
    assert response.json()["my_position"] == {
        "is_leading": False,
        "status": "outbid",
        "last_amount": "1000.00",
        "rank": 3,
    }

    my_bids = client.get("/api/me/bids")
    assert my_bids.status_code == HTTPStatus.OK
    bid_row = my_bids.json()["results"][0]
    assert bid_row["lot_id"] == str(lot.pk)
    assert bid_row["lot_code"] == lot.code
    assert bid_row["lot_title"] == lot.title


def test_bid_post_returns_original_replay_and_contextual_funds_error(
    client: Client, lot: Lot, bidder: User, login
) -> None:
    wallet = Wallet.objects.get(user=bidder)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))
    login(bidder)
    key = str(uuid.uuid4())
    body = {"amount": "1000.00", "client_bid_id": key}

    first = client.post(
        f"{LOTS_URL}/{lot.pk}/bids",
        data=body,
        content_type="application/json",
    )
    replay = client.post(
        f"{LOTS_URL}/{lot.pk}/bids",
        data=body,
        content_type="application/json",
    )

    assert first.status_code == HTTPStatus.CREATED
    assert replay.status_code == HTTPStatus.OK
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json() == first.json()

    no_funds = User.objects.create_user(
        email="http-empty@example.com",
        password="test-password-123",
        role="BIDDER",
    )
    login(no_funds)
    failure = client.post(
        f"{LOTS_URL}/{lot.pk}/bids",
        data={"amount": "1100.00"},
        content_type="application/json",
    )
    assert failure.status_code == HTTPStatus.CONFLICT
    assert failure.json()["code"] == "INSUFFICIENT_FUNDS"
    assert failure.json()["available"] == "0.00"
    assert failure.json()["minimum_bid"] == "1100.00"


def test_detail_of_unknown_lot_returns_404(client: Client) -> None:
    response = client.get(f"{LOTS_URL}/{uuid.uuid4()}")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_owner_cancels_lot_without_bids(
    client: Client,
    seller: User,
    lot: Lot,
    login,
) -> None:
    login(seller)

    response = client.post(
        f"{LOTS_URL}/{lot.id}/cancel",
        data={"reason": "item indisponível"},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["status"] == "cancelled"
    assert payload["state_version"] == 2

    lot.refresh_from_db()
    assert lot.is_cancelled
    assert lot.cancelled_by_id == seller.id
    assert lot.cancel_reason == "item indisponível"
    assert lot.state_version == 2

    listing = client.get(LOTS_URL).json()
    assert str(lot.id) not in result_ids(listing)


def test_cancel_lot_with_bids_returns_conflict(
    client: Client,
    seller: User,
    lot: Lot,
    login,
) -> None:
    lot.bids_count = 1
    lot.save()
    login(seller)

    response = client.post(
        f"{LOTS_URL}/{lot.id}/cancel",
        data={},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "LOT_HAS_BIDS"

    lot.refresh_from_db()
    assert not lot.is_cancelled
    assert lot.state_version == 1


def test_cancel_lot_by_other_seller_is_forbidden(
    client: Client,
    other_seller: User,
    lot: Lot,
    login,
) -> None:
    login(other_seller)

    response = client.post(
        f"{LOTS_URL}/{lot.id}/cancel",
        data={},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["code"] == "LOT_NOT_OWNED"

    lot.refresh_from_db()
    assert not lot.is_cancelled


def test_cancel_lot_after_ends_at_returns_conflict(
    client: Client,
    seller: User,
    lot: Lot,
    login,
) -> None:
    now = timezone.now()
    Lot.objects.filter(pk=lot.pk).update(
        starts_at=now - timedelta(hours=3),
        ends_at=now - timedelta(hours=1),
        original_ends_at=now - timedelta(hours=1),
    )
    login(seller)

    response = client.post(
        f"{LOTS_URL}/{lot.id}/cancel",
        data={},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["code"] == "LOT_ENDED"

    lot.refresh_from_db()
    assert not lot.is_cancelled


def test_cancel_lot_twice_returns_conflict(
    client: Client,
    seller: User,
    lot: Lot,
    login,
) -> None:
    login(seller)
    url = f"{LOTS_URL}/{lot.id}/cancel"

    first = client.post(url, data={}, content_type="application/json")
    second = client.post(url, data={}, content_type="application/json")

    assert first.status_code == HTTPStatus.OK
    assert second.status_code == HTTPStatus.CONFLICT
    assert second.json()["code"] == "LOT_CANCELLED"


def test_cancel_unknown_lot_returns_404(
    client: Client,
    seller: User,
    login,
) -> None:
    login(seller)

    response = client.post(
        f"{LOTS_URL}/{uuid.uuid4()}/cancel",
        data={},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["code"] == "LOT_NOT_FOUND"
