"""Integração com o catálogo externo da Art Institute of Chicago."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, Self, cast
from uuid import UUID

import httpx
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from auctions.models import CatalogItem
from auctions.selectors import search_cached_catalog

if TYPE_CHECKING:
    from datetime import datetime
    from types import TracebackType

type JsonValue = (
    str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
)

_ARTIC_BASE_URL = "https://api.artic.edu/api/v1/artworks"
_ARTIC_PAGE_URL = "https://www.artic.edu/artworks"
_ARTIC_IMAGE_URL = "https://www.artic.edu/iiif/2"
_ARTIC_FIELDS = (
    "id",
    "title",
    "description",
    "image_id",
    "thumbnail",
    "artist_display",
    "date_display",
    "medium_display",
    "department_title",
    "classification_title",
    "place_of_origin",
    "credit_line",
)
_ATTRIBUTE_KEYS = (
    "artist_display",
    "date_display",
    "medium_display",
    "department_title",
    "place_of_origin",
    "credit_line",
)
_DESCRIPTION_KEYS = ("artist_display", "date_display", "medium_display")
_CIRCUIT_FAILURES_KEY = "auctions:catalog:circuit:failures"
_CIRCUIT_OPEN_UNTIL_KEY = "auctions:catalog:circuit:open_until"
_SEARCH_CACHE_PREFIX = "auctions:catalog:search"


@dataclass(frozen=True, slots=True)
class ExternalItem:
    """Item normalizado recebido de um provedor de catálogo."""

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
    fetched_at: datetime


@dataclass(frozen=True, slots=True)
class CatalogSearchResult:
    """Resultado de uma busca de catálogo, com a origem dos dados."""

    items: list[CatalogItem]
    from_cache: bool
    degraded: bool = False


class CatalogError(Exception):
    """Erro base das operações de catálogo."""


class CatalogUnavailableError(CatalogError):
    """O provedor externo não está disponível."""

    code = "CATALOG_UNAVAILABLE"
    detail = (
        "Catálogo temporariamente indisponível. Tente novamente em instantes."
    )

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class CatalogItemNotFoundError(CatalogError):
    """O item solicitado não existe no cache local."""

    code = "CATALOG_ITEM_NOT_FOUND"
    detail = "Item de catálogo não encontrado."

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class CatalogProvider(Protocol):
    """Contrato mínimo de um provedor de catálogo."""

    def search(self, query: str, limit: int) -> list[ExternalItem]:
        """Busca itens por texto."""
        ...

    def get_item(self, external_id: str) -> ExternalItem:
        """Obtém um item pelo identificador externo."""
        ...


def _as_text(value: JsonValue) -> str:
    """Converte um valor JSON simples em texto, descartando o restante."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _build_attributes(data: dict[str, JsonValue]) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for key in _ATTRIBUTE_KEYS:
        value = _as_text(data.get(key))
        if value:
            attributes[key] = value
    return attributes


def _build_description(
    data: dict[str, JsonValue],
    attributes: dict[str, str],
) -> str:
    parts: list[str] = []
    raw_description = _as_text(data.get("description"))
    if raw_description:
        parts.append(raw_description)
    summary = " — ".join(
        attributes[key] for key in _DESCRIPTION_KEYS if key in attributes
    )
    if summary:
        parts.append(summary)
    return "\n\n".join(parts)


def _normalize_item(data: dict[str, JsonValue]) -> ExternalItem:
    external_id = _as_text(data.get("id"))
    image_id = _as_text(data.get("image_id"))
    source_url = (
        f"{_ARTIC_PAGE_URL}/{external_id}" if external_id else _ARTIC_PAGE_URL
    )
    image_url = (
        f"{_ARTIC_IMAGE_URL}/{image_id}/full/843,/0/default.jpg"
        if image_id
        else source_url
    )
    thumbnail_url = (
        f"{_ARTIC_IMAGE_URL}/{image_id}/full/400,/0/default.jpg"
        if image_id
        else ""
    )
    attributes = _build_attributes(data)
    category = _as_text(data.get("department_title")) or _as_text(
        data.get("classification_title"),
    )
    return ExternalItem(
        source="artic",
        external_id=external_id,
        title=_as_text(data.get("title")) or "Obra sem título",
        description=_build_description(data, attributes),
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        source_url=source_url,
        category=category,
        attributes=attributes,
        raw_payload=data,
        fetched_at=timezone.now(),
    )


def _circuit_failures() -> int:
    value = cache.get(_CIRCUIT_FAILURES_KEY, 0)
    return value if isinstance(value, int) else 0


def _is_circuit_open() -> bool:
    value = cache.get(_CIRCUIT_OPEN_UNTIL_KEY, 0.0)
    open_until = float(value) if isinstance(value, (int, float)) else 0.0
    return open_until > time.time()


def _record_failure() -> None:
    failures = _circuit_failures() + 1
    cache.set(_CIRCUIT_FAILURES_KEY, failures, timeout=None)
    threshold = max(1, int(settings.CATALOG_CIRCUIT_THRESHOLD))
    if failures < threshold:
        return
    cooldown = max(0, int(settings.CATALOG_CIRCUIT_COOLDOWN_SECONDS))
    cache.set(
        _CIRCUIT_OPEN_UNTIL_KEY,
        time.time() + cooldown,
        timeout=None,
    )


def _reset_circuit() -> None:
    cache.delete(_CIRCUIT_FAILURES_KEY)
    cache.delete(_CIRCUIT_OPEN_UNTIL_KEY)


def _search_cache_key(query: str, limit: int) -> str:
    digest = hashlib.sha256(
        query.strip().casefold().encode("utf-8"),
    ).hexdigest()
    return f"{_SEARCH_CACHE_PREFIX}:{digest}:{limit}"


def _read_search_cache(query: str, limit: int) -> list[CatalogItem]:
    raw_ids = cache.get(_search_cache_key(query, limit))
    if not isinstance(raw_ids, list):
        return []
    item_ids: list[UUID] = []
    for raw_id in raw_ids:
        if not isinstance(raw_id, str):
            continue
        try:
            item_ids.append(UUID(raw_id))
        except ValueError:
            continue
    if not item_ids:
        return []
    found = CatalogItem.objects.in_bulk(item_ids)
    return [found[item_id] for item_id in item_ids if item_id in found]


def _write_search_cache(
    query: str, limit: int, items: list[CatalogItem]
) -> None:
    seconds = int(settings.CATALOG_SEARCH_CACHE_SECONDS)
    if seconds <= 0 or not items:
        return
    cache.set(
        _search_cache_key(query, limit),
        [str(item.id) for item in items],
        timeout=seconds,
    )


class ArticProvider:
    """Provedor do catálogo público da Art Institute of Chicago."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=float(settings.CATALOG_HTTP_TIMEOUT_SECONDS),
            follow_redirects=True,
        )

    def close(self) -> None:
        """Fecha o client HTTP apenas quando ele foi criado internamente."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def search(self, query: str, limit: int) -> list[ExternalItem]:
        """Busca obras na AIC e devolve os itens normalizados."""
        payload = self._get_json(
            f"{_ARTIC_BASE_URL}/search",
            {
                "q": query,
                "page": 1,
                "limit": max(1, limit),
                "fields": ",".join(_ARTIC_FIELDS),
            },
        )
        data = payload.get("data")
        if not isinstance(data, list):
            _record_failure()
            message = "Resposta inválida do catálogo externo."
            raise CatalogUnavailableError(message)
        return [
            _normalize_item(entry) for entry in data if isinstance(entry, dict)
        ]

    def get_item(self, external_id: str) -> ExternalItem:
        """Obtém uma obra específica da AIC."""
        payload = self._get_json(
            f"{_ARTIC_BASE_URL}/{external_id}",
            {"fields": ",".join(_ARTIC_FIELDS)},
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            message = "Obra não encontrada no catálogo externo."
            raise CatalogItemNotFoundError(message)
        return _normalize_item(data)

    def _get_json(
        self,
        url: str,
        params: dict[str, str | int],
    ) -> dict[str, JsonValue]:
        if _is_circuit_open():
            message = "Catálogo externo temporariamente bloqueado."
            raise CatalogUnavailableError(message)

        attempts = max(1, int(settings.CATALOG_HTTP_MAX_ATTEMPTS))
        backoff = max(0.0, float(settings.CATALOG_HTTP_BACKOFF_SECONDS))
        last_error: Exception | None = None
        headers = {"User-Agent": str(settings.CATALOG_USER_AGENT)}
        timeout = float(settings.CATALOG_HTTP_TIMEOUT_SECONDS)

        for attempt in range(attempts):
            try:
                response = self._client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                self._wait_before_retry(attempt, attempts, backoff)
                continue

            if response.status_code == httpx.codes.NOT_FOUND:
                message = "Obra não encontrada no catálogo externo."
                raise CatalogItemNotFoundError(message)

            retryable = (
                response.status_code == httpx.codes.TOO_MANY_REQUESTS
                or response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR
            )
            if retryable:
                last_error = httpx.HTTPStatusError(
                    "Resposta temporariamente indisponível.",
                    request=response.request,
                    response=response,
                )
                self._wait_before_retry(attempt, attempts, backoff)
                continue

            try:
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                _record_failure()
                message = "Resposta inválida do catálogo externo."
                raise CatalogUnavailableError(message) from exc

            if not isinstance(payload, dict):
                _record_failure()
                message = "Resposta inválida do catálogo externo."
                raise CatalogUnavailableError(message)

            _reset_circuit()
            return cast("dict[str, JsonValue]", payload)

        _record_failure()
        message = "Catálogo externo indisponível no momento."
        raise CatalogUnavailableError(message) from last_error

    @staticmethod
    def _wait_before_retry(
        attempt: int, attempts: int, backoff: float
    ) -> None:
        if attempt + 1 < attempts and backoff > 0:
            time.sleep(backoff * (2**attempt))


def get_catalog_provider() -> CatalogProvider:
    """Instancia o provedor configurado para a aplicação."""
    provider_name = str(settings.CATALOG_PROVIDER).strip().lower()
    if provider_name == "artic":
        return ArticProvider()
    message = f"Provedor de catálogo não suportado: {provider_name!r}."
    raise CatalogUnavailableError(message)


def persist_external_item(item: ExternalItem) -> CatalogItem:
    """Persiste um item externo como snapshot imutável, uma única vez."""
    catalog_item, _ = CatalogItem.objects.get_or_create(
        source=item.source,
        external_id=item.external_id,
        defaults={
            "title": item.title,
            "description": item.description,
            "image_url": item.image_url,
            "thumbnail_url": item.thumbnail_url,
            "source_url": item.source_url,
            "category": item.category,
            "attributes": dict(item.attributes),
            "raw_payload": dict(item.raw_payload),
            "fetched_at": item.fetched_at,
        },
    )
    return catalog_item


def _cached_fallback(query: str, limit: int) -> CatalogSearchResult:
    cached_items = _read_search_cache(query, limit)
    if cached_items:
        return CatalogSearchResult(
            items=cached_items,
            from_cache=True,
            degraded=True,
        )
    database_items = list(search_cached_catalog(query, limit))
    if not database_items:
        # A busca textual não encontrou nada: mostra o acervo local completo
        # para que o leiloeiro ainda consiga publicar um lote enquanto a AIC
        # estiver indisponível.
        database_items = list(search_cached_catalog("", limit))
    if not database_items:
        message = (
            "Catálogo externo indisponível e nenhum item local cadastrado. "
            "Execute o seed de demonstração ou tente novamente em instantes."
        )
        raise CatalogUnavailableError(message)
    return CatalogSearchResult(
        items=database_items,
        from_cache=True,
        degraded=True,
    )


def search_catalog(query: str, limit: int = 20) -> CatalogSearchResult:
    """Busca no provedor, persiste os itens e cai para o cache local."""
    safe_limit = max(1, limit)

    try:
        provider = get_catalog_provider()
    except CatalogError:
        return _cached_fallback(query, safe_limit)

    try:
        try:
            external_items = provider.search(query, safe_limit)
        except CatalogError:
            return _cached_fallback(query, safe_limit)
        items = [persist_external_item(item) for item in external_items]
    finally:
        if isinstance(provider, ArticProvider):
            provider.close()

    _write_search_cache(query, safe_limit, items)
    return CatalogSearchResult(items=items, from_cache=False)


def get_catalog_item(item_id: UUID) -> CatalogItem:
    """Recupera um item já persistido, sem consultar a API externa."""
    catalog_item = CatalogItem.objects.filter(pk=item_id).first()
    if catalog_item is None:
        raise CatalogItemNotFoundError
    return catalog_item
