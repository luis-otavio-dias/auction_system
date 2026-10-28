"""Download e cache local de imagens de lotes."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import httpx
from django.conf import settings

_SAFE_STEM_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")
_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
}


def _safe_stem(external_id: str) -> str:
    stem = _SAFE_STEM_PATTERN.sub("-", external_id.strip()).strip("-_")
    return stem[:48] or "item"


def _extension_for(content_type: str) -> str:
    return _EXTENSIONS.get(content_type, ".img")


def _download_image(image_url: str, external_id: str) -> str | None:
    media_root = Path(settings.MEDIA_ROOT)
    filename = ""
    try:
        user_agent = str(settings.CATALOG_USER_AGENT)
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            response = client.get(
                image_url,
                timeout=5.0,
                headers={"User-Agent": user_agent},
            )
            if response.status_code != httpx.codes.OK:
                return None

            raw_content_type = response.headers.get("content-type", "")
            content_type = raw_content_type.split(";", 1)[0].strip().lower()
            if not content_type.startswith("image/"):
                return None

            payload = response.content
            if not payload:
                return None

            directory = media_root / "lots"
            directory.mkdir(parents=True, exist_ok=True)
            filename = (
                f"{_safe_stem(external_id)}-{uuid.uuid4().hex[:12]}"
                f"{_extension_for(content_type)}"
            )
            (directory / filename).write_bytes(payload)
    except httpx.HTTPError, OSError, ValueError:
        return None
    else:
        media_url = str(settings.MEDIA_URL).rstrip("/")
        return f"{media_url}/lots/{filename}"


def cache_remote_image(image_url: str, external_id: str) -> str | None:
    """Baixa uma imagem remota para ``MEDIA_ROOT/lots`` sem propagar falhas."""
    if not image_url:
        return None

    # Imagens do acervo local (static/media) já estão prontas para uso.
    if image_url.startswith(("/", "./")):
        return image_url

    return _download_image(image_url, external_id)
