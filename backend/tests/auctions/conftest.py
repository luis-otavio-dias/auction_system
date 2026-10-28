"""Fixtures compartilhadas dos testes do app de leilões."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.utils import timezone

from auctions.models import CatalogItem, Lot
from users.models import User

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.test import Client

TEST_PASSWORD = "test-password-123"


@pytest.fixture
def catalog_item() -> CatalogItem:
    return CatalogItem.objects.create(
        source="artic",
        external_id="129884",
        title="Starry Night and the Astronauts",
        description="Obra de Alma Thomas.",
        image_url=(
            "https://www.artic.edu/iiif/2/"
            "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9/full/843,/0/default.jpg"
        ),
        thumbnail_url=(
            "https://www.artic.edu/iiif/2/"
            "e966799b-97ee-1cc6-bd2f-a94b4b8bb8f9/full/400,/0/default.jpg"
        ),
        source_url="https://www.artic.edu/artworks/129884",
        category="Contemporary Art",
        attributes={
            "artist_display": "Alma Thomas",
            "date_display": "1972",
            "medium_display": "Acrylic on canvas",
        },
        raw_payload={"id": 129884, "title": "Starry Night"},
    )


@pytest.fixture
def other_catalog_item() -> CatalogItem:
    return CatalogItem.objects.create(
        source="artic",
        external_id="8741",
        title="Water Lilies",
        description="Obra de Claude Monet.",
        image_url=(
            "https://www.artic.edu/iiif/2/"
            "3c27b499-af56-f0d5-ab28-2b1d3ca5a1a3/full/843,/0/default.jpg"
        ),
        source_url="https://www.artic.edu/artworks/8741",
        category="Impressionism",
        attributes={
            "artist_display": "Claude Monet",
            "date_display": "1906",
            "medium_display": "Oil on canvas",
        },
        raw_payload={"id": 8741, "title": "Water Lilies"},
    )


@pytest.fixture
def other_seller() -> User:
    return User.objects.create_user(
        email="other-seller@example.com",
        password=TEST_PASSWORD,
        role="SELLER",
        full_name="Other Seller",
    )


@pytest.fixture
def lot(
    seller: User,
    catalog_item: CatalogItem,
) -> Lot:
    now = timezone.now()
    return Lot.objects.create(
        seller=seller,
        catalog_item=catalog_item,
        title=catalog_item.title,
        description=catalog_item.description,
        image_url=catalog_item.image_url,
        image_remote_url=catalog_item.image_url,
        image_cached=False,
        source=catalog_item.source,
        external_id=catalog_item.external_id,
        source_url=catalog_item.source_url,
        category=catalog_item.category,
        attributes=catalog_item.attributes,
        starting_bid=Decimal("1000.00"),
        min_increment=Decimal("100.00"),
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        original_ends_at=now + timedelta(hours=1),
    )


@pytest.fixture
def login(client: Client) -> Callable[[User], None]:
    """Autentica o client de teste por cookie JWT."""

    def _login(user: User) -> None:
        response = client.post(
            "/api/auth/token/",
            data={"email": user.email, "password": TEST_PASSWORD},
            content_type="application/json",
        )
        assert response.status_code == 200

    return _login
