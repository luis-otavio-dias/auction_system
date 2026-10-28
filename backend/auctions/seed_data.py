"""Fixtures locais do catálogo usadas pelo seed de demonstração."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from auctions.services.catalog import JsonValue

_CATALOG_STATIC_URL = "/static/auctions/catalog"


@dataclass(frozen=True, slots=True)
class CatalogSeedItem:
    """Item de catálogo pronto para ser persistido sem acesso à rede."""

    source: str
    external_id: str
    title: str
    description: str
    image_url: str
    thumbnail_url: str
    source_url: str
    category: str
    attributes: dict[str, str]
    raw_payload: dict[str, JsonValue]


CATALOG_SEED_ITEMS: tuple[CatalogSeedItem, ...] = (
    CatalogSeedItem(
        source="artic",
        external_id="27992",
        title="Uma Tarde de Domingo na Ilha de La Grande Jatte",
        description=(
            "Cena de lazer à beira do rio Sena, marco do pontilhismo "
            "e uma das obras mais conhecidas da Art Institute of Chicago."
        ),
        image_url=f"{_CATALOG_STATIC_URL}/grande-jatte.jpg",
        thumbnail_url=f"{_CATALOG_STATIC_URL}/grande-jatte-thumb.jpg",
        source_url="https://www.artic.edu/artworks/27992",
        category="Painting and Sculpture of Europe",
        attributes={
            "artist_display": "Georges Seurat (French, 1859-1891)",
            "date_display": "1884-86",
            "medium_display": "Oil on canvas",
            "department_title": "Painting and Sculpture of Europe",
            "place_of_origin": "France",
            "credit_line": "Helen Birch Bartlett Memorial Collection",
        },
        raw_payload={
            "id": 27992,
            "title": "A Sunday on La Grande Jatte — 1884",
            "image_id": "2d484387-2509-5e8e-2c43-22f9981972eb",
        },
    ),
    CatalogSeedItem(
        source="artic",
        external_id="6565",
        title="American Gothic",
        description=(
            "Retrato de um casal rural diante de uma casa de estilo gótico, "
            "ícone da pintura americana do século XX."
        ),
        image_url=f"{_CATALOG_STATIC_URL}/american-gothic.jpg",
        thumbnail_url=f"{_CATALOG_STATIC_URL}/american-gothic-thumb.jpg",
        source_url="https://www.artic.edu/artworks/6565",
        category="Arts of the Americas",
        attributes={
            "artist_display": "Grant Wood (American, 1891-1942)",
            "date_display": "1930",
            "medium_display": "Oil on Beaver Board",
            "department_title": "Arts of the Americas",
            "place_of_origin": "Cedar Rapids",
            "credit_line": "Friends of American Art Collection",
        },
        raw_payload={
            "id": 6565,
            "title": "American Gothic",
            "image_id": "b272df73-a965-ac37-4172-be4e99483637",
        },
    ),
    CatalogSeedItem(
        source="artic",
        external_id="111628",
        title="Nighthawks",
        description=(
            "Clientes solitários em um café noturno iluminado, uma das "
            "imagens mais reconhecíveis da arte norte-americana."
        ),
        image_url=f"{_CATALOG_STATIC_URL}/nighthawks.jpg",
        thumbnail_url=f"{_CATALOG_STATIC_URL}/nighthawks-thumb.jpg",
        source_url="https://www.artic.edu/artworks/111628",
        category="Arts of the Americas",
        attributes={
            "artist_display": "Edward Hopper (American, 1882-1967)",
            "date_display": "1942",
            "medium_display": "Oil on canvas",
            "department_title": "Arts of the Americas",
            "place_of_origin": "United States",
            "credit_line": "Friends of American Art Collection",
        },
        raw_payload={
            "id": 111628,
            "title": "Nighthawks",
            "image_id": "831a05de-d3f6-f4fa-a460-23008dd58dda",
        },
    ),
    CatalogSeedItem(
        source="artic",
        external_id="28560",
        title="O Quarto",
        description=(
            "Interior doméstico reduzido a formas e cores intensas, "
            "pintado por Van Gogh em Saint-Rémy."
        ),
        image_url=f"{_CATALOG_STATIC_URL}/the-bedroom.jpg",
        thumbnail_url=f"{_CATALOG_STATIC_URL}/the-bedroom-thumb.jpg",
        source_url="https://www.artic.edu/artworks/28560",
        category="Painting and Sculpture of Europe",
        attributes={
            "artist_display": "Vincent van Gogh (Dutch, 1853-1890)",
            "date_display": "1889",
            "medium_display": "Oil on canvas",
            "department_title": "Painting and Sculpture of Europe",
            "place_of_origin": "Saint-Rémy-de-Provence",
            "credit_line": "Helen Birch Bartlett Memorial Collection",
        },
        raw_payload={
            "id": 28560,
            "title": "The Bedroom",
            "image_id": "6644829f-f292-c5c4-a73c-0356a6fdbf0d",
        },
    ),
)
