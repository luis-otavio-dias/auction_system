"""Testes de catálogo, seed e integração de lotes com imagens."""

from __future__ import annotations

import time
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from auctions import views
from auctions.management.commands.seed_demo import (
    DEMO_BIDDER_EMAILS,
    DEMO_PASSWORD,
    DEMO_SELLER_EMAIL,
)
from auctions.models import CatalogItem, Lot, Receipt
from auctions.services.catalog import (
    ArticProvider,
    CatalogItemNotFoundError,
    CatalogSearchResult,
    CatalogUnavailableError,
    ExternalItem,
    get_catalog_item,
    search_catalog,
)
from auctions.services.images import cache_remote_image
from auctions.services.lots import create_lot
from users.models import User
from wallet.models import Wallet, WalletTransaction

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.test import Client

ARTIC_EXTERNAL_ID = "129884"
ARTIC_IMAGE_ID = "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9"
ARTIC_IMAGE_URL = (
    f"https://www.artic.edu/iiif/2/{ARTIC_IMAGE_ID}/full/843,/0/default.jpg"
)
ARTIC_THUMBNAIL_URL = (
    f"https://www.artic.edu/iiif/2/{ARTIC_IMAGE_ID}/full/400,/0/default.jpg"
)


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Isola o circuit breaker do provider entre os testes."""
    cache.clear()


def _artic_artwork() -> dict[str, str | int]:
    return {
        "id": int(ARTIC_EXTERNAL_ID),
        "title": "Starry Night and the Astronauts",
        "image_id": ARTIC_IMAGE_ID,
        "artist_display": "Alma Thomas\nAmerican, 1891-1978",
        "date_display": "1972",
        "medium_display": "Acrylic on canvas",
        "department_title": "Contemporary Art",
        "classification_title": "Painting",
        "place_of_origin": "United States",
        "credit_line": "Gift of the artist",
    }


def _artic_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _external_item(
    external_id: str = ARTIC_EXTERNAL_ID,
    title: str = "Starry Night and the Astronauts",
) -> ExternalItem:
    return ExternalItem(
        source="artic",
        external_id=external_id,
        title=title,
        description="Obra de Alma Thomas.",
        image_url=ARTIC_IMAGE_URL,
        thumbnail_url=ARTIC_THUMBNAIL_URL,
        source_url=f"https://www.artic.edu/artworks/{external_id}",
        category="Contemporary Art",
        attributes={
            "artist_display": "Alma Thomas",
            "date_display": "1972",
            "medium_display": "Acrylic on canvas",
        },
        raw_payload={"id": int(external_id), "title": title},
        fetched_at=timezone.now(),
    )


class _FakeProvider:
    def __init__(self, items: list[ExternalItem]) -> None:
        self._items = items

    def search(self, query: str, limit: int) -> list[ExternalItem]:
        _ = (query, limit)
        return list(self._items)

    def get_item(self, external_id: str) -> ExternalItem:
        return next(
            item for item in self._items if item.external_id == external_id
        )


class _FailingProvider:
    def search(self, query: str, limit: int) -> list[ExternalItem]:
        _ = (query, limit)
        raise CatalogUnavailableError

    def get_item(self, external_id: str) -> ExternalItem:
        _ = external_id
        raise CatalogUnavailableError


# --- ArticProvider -------------------------------------------------------


@pytest.mark.django_db
def test_artic_provider_get_item_normalizes_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/api/v1/artworks/{ARTIC_EXTERNAL_ID}"
        return httpx.Response(200, json={"data": _artic_artwork()})

    provider = ArticProvider(client=_artic_client(handler))

    item = provider.get_item(ARTIC_EXTERNAL_ID)

    assert item.source == "artic"
    assert item.external_id == ARTIC_EXTERNAL_ID
    assert item.title == "Starry Night and the Astronauts"
    assert item.image_url == ARTIC_IMAGE_URL
    assert item.thumbnail_url == ARTIC_THUMBNAIL_URL
    assert item.source_url == (
        f"https://www.artic.edu/artworks/{ARTIC_EXTERNAL_ID}"
    )
    assert item.category == "Contemporary Art"
    assert item.attributes == {
        "artist_display": "Alma Thomas\nAmerican, 1891-1978",
        "date_display": "1972",
        "medium_display": "Acrylic on canvas",
        "department_title": "Contemporary Art",
        "place_of_origin": "United States",
        "credit_line": "Gift of the artist",
    }
    assert "classification_title" not in item.attributes
    assert "Alma Thomas" in item.description
    assert "1972" in item.description
    assert "Acrylic on canvas" in item.description
    assert item.raw_payload["id"] == int(ARTIC_EXTERNAL_ID)
    assert item.fetched_at.tzinfo is not None


@pytest.mark.django_db
def test_artic_provider_retries_5xx_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(500, json={"detail": "erro interno"})

    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    provider = ArticProvider(client=_artic_client(handler))

    with pytest.raises(CatalogUnavailableError):
        provider.get_item(ARTIC_EXTERNAL_ID)

    assert len(calls) == 2


@pytest.mark.django_db
def test_artic_provider_retries_timeout_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        message = "tempo esgotado"
        raise httpx.ReadTimeout(message, request=request)

    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    provider = ArticProvider(client=_artic_client(handler))

    with pytest.raises(CatalogUnavailableError):
        provider.get_item(ARTIC_EXTERNAL_ID)

    assert len(calls) == 2


@pytest.mark.django_db
def test_artic_provider_falls_back_to_source_url_without_image_id() -> None:
    payload = _artic_artwork()
    payload.pop("image_id")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": payload})

    provider = ArticProvider(client=_artic_client(handler))

    item = provider.get_item(ARTIC_EXTERNAL_ID)

    assert (
        item.image_url == f"https://www.artic.edu/artworks/{ARTIC_EXTERNAL_ID}"
    )
    assert item.thumbnail_url == ""


# --- search_catalog ------------------------------------------------------


@pytest.mark.django_db
def test_search_catalog_persists_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _external_item()
    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        lambda: _FakeProvider([item]),
    )

    result = search_catalog("starry")

    assert result.from_cache is False
    assert result.degraded is False
    assert len(result.items) == 1
    persisted = CatalogItem.objects.get(
        source="artic",
        external_id=ARTIC_EXTERNAL_ID,
    )
    assert result.items[0].pk == persisted.pk
    assert persisted.title == item.title
    assert persisted.attributes == item.attributes


@pytest.mark.django_db
def test_search_catalog_uses_database_cache_when_provider_fails(
    monkeypatch: pytest.MonkeyPatch,
    catalog_item: CatalogItem,
) -> None:
    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        _FailingProvider,
    )

    result = search_catalog("Starry")

    assert result.from_cache is True
    assert result.degraded is True
    assert [item.pk for item in result.items] == [catalog_item.pk]


@pytest.mark.django_db
def test_search_catalog_falls_back_to_all_local_items_without_match(
    monkeypatch: pytest.MonkeyPatch,
    catalog_item: CatalogItem,
) -> None:
    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        _FailingProvider,
    )

    result = search_catalog("termo-que-nao-existe")

    assert result.from_cache is True
    assert result.degraded is True
    assert [item.pk for item in result.items] == [catalog_item.pk]


@pytest.mark.django_db
def test_search_catalog_falls_back_when_provider_factory_fails(
    monkeypatch: pytest.MonkeyPatch,
    catalog_item: CatalogItem,
) -> None:
    def failing_factory() -> None:
        raise CatalogUnavailableError

    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        failing_factory,
    )

    result = search_catalog("Starry")

    assert result.from_cache is True
    assert result.degraded is True
    assert [item.pk for item in result.items] == [catalog_item.pk]


@pytest.mark.django_db
def test_search_catalog_raises_without_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        _FailingProvider,
    )

    with pytest.raises(CatalogUnavailableError):
        search_catalog("resultado-inexistente")


@pytest.mark.django_db
def test_artic_provider_rejects_malformed_search_payload() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": "não é uma lista"})

    provider = ArticProvider(client=_artic_client(handler))

    with pytest.raises(CatalogUnavailableError):
        provider.search("starry", 10)


@pytest.mark.django_db
def test_get_catalog_item_never_calls_provider(
    monkeypatch: pytest.MonkeyPatch,
    catalog_item: CatalogItem,
) -> None:
    def explode() -> None:
        message = "provider não deve ser chamado"
        raise AssertionError(message)

    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        explode,
    )

    item = get_catalog_item(catalog_item.pk)

    assert item.pk == catalog_item.pk
    assert item.image_url == catalog_item.image_url


@pytest.mark.django_db
def test_get_catalog_item_missing_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "auctions.services.catalog.get_catalog_provider",
        _FailingProvider,
    )

    with pytest.raises(CatalogItemNotFoundError):
        get_catalog_item(uuid.uuid4())


# --- criação de lote e imagem -------------------------------------------


def test_cache_remote_image_keeps_local_paths_without_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: str, **_kwargs: str) -> None:
        message = "imagem local não deve acessar a rede"
        raise AssertionError(message)

    monkeypatch.setattr(httpx, "Client", forbidden)

    assert cache_remote_image("/static/auctions/catalog/item.jpg", "1") == (
        "/static/auctions/catalog/item.jpg"
    )


@pytest.mark.django_db
def test_create_lot_falls_back_to_remote_image(
    monkeypatch: pytest.MonkeyPatch,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    monkeypatch.setattr(
        "auctions.services.lots.cache_remote_image",
        lambda _url, _external_id: None,
    )
    now = timezone.now()

    lot = create_lot(
        seller=seller,
        catalog_item=catalog_item,
        starts_at=now,
        ends_at=now + timedelta(hours=1),
        starting_bid=Decimal("100.00"),
        min_increment=Decimal("10.00"),
    )

    assert lot.image_cached is False
    assert lot.image_remote_url == catalog_item.image_url
    assert lot.image_url == catalog_item.image_url
    assert lot.pk is not None


@pytest.mark.django_db
def test_create_lot_uses_cached_image(
    monkeypatch: pytest.MonkeyPatch,
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    monkeypatch.setattr(
        "auctions.services.lots.cache_remote_image",
        lambda _url, _external_id: "/media/lots/test.jpg",
    )
    now = timezone.now()

    lot = create_lot(
        seller=seller,
        catalog_item=catalog_item,
        starts_at=now,
        ends_at=now + timedelta(hours=1),
        starting_bid=Decimal("100.00"),
        min_increment=Decimal("10.00"),
    )

    assert lot.image_cached is True
    assert lot.image_url == "/media/lots/test.jpg"
    assert lot.image_remote_url == catalog_item.image_url


# --- seed ----------------------------------------------------------------


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: str, **_kwargs: str) -> None:
        message = "seed não deve acessar a rede"
        raise AssertionError(message)

    monkeypatch.setattr(
        "auctions.services.images.cache_remote_image",
        forbidden,
    )
    monkeypatch.setattr(
        "auctions.services.lots.cache_remote_image",
        forbidden,
    )
    monkeypatch.setattr(httpx, "Client", forbidden)

    call_command("seed_demo")
    first_catalog_count = CatalogItem.objects.count()
    first_lot_count = Lot.objects.count()

    call_command("seed_demo")

    assert first_catalog_count >= 3
    assert CatalogItem.objects.count() == first_catalog_count
    assert Lot.objects.count() == first_lot_count
    assert first_lot_count >= 1
    distinct_pairs = CatalogItem.objects.values(
        "source",
        "external_id",
    ).distinct()
    assert CatalogItem.objects.count() == distinct_pairs.count()


@pytest.mark.django_db
def test_seed_demo_updates_password_of_existing_demo_accounts() -> None:
    User.objects.create_user(
        email=DEMO_SELLER_EMAIL,
        password="old-password-123",
        role=User.Role.SELLER,
    )
    for email in DEMO_BIDDER_EMAILS:
        User.objects.create_user(
            email=email,
            password="old-password-123",
            role=User.Role.BIDDER,
        )

    call_command("seed_demo")

    for email in (DEMO_SELLER_EMAIL, *DEMO_BIDDER_EMAILS):
        assert User.objects.get(email=email).check_password(DEMO_PASSWORD)


@pytest.mark.django_db
def test_seed_demo_new_live_preserves_previous_live_lot() -> None:
    call_command("seed_demo")
    current_lots = Lot.objects.filter(
        seller__email="leiloeiro@demo.com",
        starts_at__lte=timezone.now(),
        ends_at__gt=timezone.now(),
        settled_at__isnull=True,
        cancelled_at__isnull=True,
    )
    previous_live_id = current_lots.values_list("pk", flat=True).first()
    assert previous_live_id is not None

    call_command("seed_demo", new_live=True)

    live_lots = Lot.objects.filter(
        seller__email="leiloeiro@demo.com",
        starts_at__lte=timezone.now(),
        ends_at__gt=timezone.now(),
        settled_at__isnull=True,
        cancelled_at__isnull=True,
    )
    assert live_lots.count() == 2
    assert live_lots.filter(pk=previous_live_id).exists()
    assert live_lots.filter(bids_count__gte=2).count() == 2


@pytest.mark.django_db
def test_seed_demo_reset_rebuilds_live_lot_and_receipt() -> None:
    call_command("seed_demo")
    bidder = User.objects.get(email="cliente1@demo.com")
    WalletTransaction.objects.create(
        wallet=Wallet.objects.get(user=bidder),
        type=WalletTransaction.Type.DEPOSIT,
        amount=Decimal("37.00"),
        balance_after=Decimal("10037.00"),
        committed_after=Decimal("0.00"),
        reference_kind=WalletTransaction.ReferenceKind.DEPOSIT,
        description="Depósito externo de teste",
    )
    call_command("seed_demo", reset=True)

    live = Lot.objects.get(
        seller__email="leiloeiro@demo.com",
        starts_at__lte=timezone.now(),
        ends_at__gt=timezone.now(),
        settled_at__isnull=True,
        cancelled_at__isnull=True,
    )
    assert live.bids_count >= 2
    assert live.bids.count() == live.bids_count
    assert live.current_winner_id is not None
    assert live.current_bid is not None
    winner = User.objects.get(pk=live.current_winner_id)
    assert Wallet.objects.get(user=winner).committed == live.current_bid
    assert Receipt.objects.filter(
        lot__seller__email="leiloeiro@demo.com"
    ).exists()
    assert WalletTransaction.objects.filter(
        wallet__user=bidder,
        description="Depósito externo de teste",
    ).exists()


# --- API -----------------------------------------------------------------


def _fake_search(
    catalog_item: CatalogItem,
) -> Callable[[str, int], CatalogSearchResult]:
    def search(query: str, limit: int = 20) -> CatalogSearchResult:
        _ = (query, limit)
        return CatalogSearchResult(items=[catalog_item], from_cache=False)

    return search


@pytest.mark.django_db
def test_catalog_search_requires_seller(
    client: Client,
    login: Callable[[User], None],
    bidder: User,
    catalog_item: CatalogItem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        views,
        "search_catalog",
        _fake_search(catalog_item),
    )

    anonymous = client.get("/api/catalog/search", {"q": "starry"})
    assert anonymous.status_code in (401, 403)

    login(bidder)
    bidder_response = client.get("/api/catalog/search", {"q": "starry"})
    assert bidder_response.status_code == 403


@pytest.mark.django_db
def test_catalog_search_returns_results_for_seller(
    client: Client,
    login: Callable[[User], None],
    seller: User,
    catalog_item: CatalogItem,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        views,
        "search_catalog",
        _fake_search(catalog_item),
    )
    login(seller)

    response = client.get("/api/catalog/search", {"q": "starry"})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["from_cache"] is False
    assert body["degraded"] is False
    assert body["results"][0]["id"] == str(catalog_item.pk)
    assert body["results"][0]["title"] == catalog_item.title


@pytest.mark.django_db
def test_catalog_search_returns_absolute_local_image_url(
    client: Client,
    login: Callable[[User], None],
    seller: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = CatalogItem.objects.create(
        source="artic",
        external_id="local-1",
        title="Obra local",
        image_url="/static/auctions/catalog/obra.jpg",
        thumbnail_url="/static/auctions/catalog/obra-thumb.jpg",
        source_url="https://www.artic.edu/artworks/local-1",
    )
    monkeypatch.setattr(
        views,
        "search_catalog",
        lambda _query, _limit=20: CatalogSearchResult(
            items=[item],
            from_cache=True,
            degraded=True,
        ),
    )
    login(seller)

    response = client.get("/api/catalog/search", {"q": "obra"})

    body = response.json()
    assert response.status_code == 200
    assert body["degraded"] is True
    assert body["results"][0]["image_url"] == (
        "http://testserver/static/auctions/catalog/obra.jpg"
    )
    assert body["results"][0]["thumbnail_url"] == (
        "http://testserver/static/auctions/catalog/obra-thumb.jpg"
    )


@pytest.mark.django_db
def test_catalog_search_returns_503_when_unavailable(
    client: Client,
    login: Callable[[User], None],
    seller: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(query: str, limit: int = 20) -> CatalogSearchResult:
        _ = (query, limit)
        raise CatalogUnavailableError

    monkeypatch.setattr(views, "search_catalog", unavailable)
    login(seller)

    response = client.get("/api/catalog/search", {"q": "starry"})

    assert response.status_code == 503
    assert response.json()["code"] == "CATALOG_UNAVAILABLE"


@pytest.mark.django_db
def test_catalog_item_detail_for_seller(
    client: Client,
    login: Callable[[User], None],
    seller: User,
    catalog_item: CatalogItem,
) -> None:
    login(seller)

    response = client.get(f"/api/catalog/items/{catalog_item.pk}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(catalog_item.pk)
    assert body["external_id"] == catalog_item.external_id
    assert "raw_payload" not in body


@pytest.mark.django_db
def test_catalog_item_detail_missing_returns_404(
    client: Client,
    login: Callable[[User], None],
    seller: User,
) -> None:
    login(seller)

    response = client.get(f"/api/catalog/items/{uuid.uuid4()}")

    assert response.status_code == 404
