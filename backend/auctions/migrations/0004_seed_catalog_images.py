"""Aponta o acervo de demonstração para as imagens empacotadas localmente.

O seed antigo usava URLs remotas da Art Institute of Chicago que passaram a
responder 403 (Cloudflare), deixando a vitrine sem imagens. Esta migração
também corrige o item 15468, que não correspondia à obra descrita.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import migrations

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from django.db.backends.base.schema import BaseDatabaseSchemaEditor

    from auctions.seed_data import CatalogSeedItem

_LEGACY_EXTERNAL_IDS = {"15468": "28560"}


def _seed_fields(seed: CatalogSeedItem) -> dict[str, object]:
    return {
        "external_id": seed.external_id,
        "title": seed.title,
        "description": seed.description,
        "image_url": seed.image_url,
        "thumbnail_url": seed.thumbnail_url,
        "source_url": seed.source_url,
        "category": seed.category,
        "attributes": dict(seed.attributes),
        "raw_payload": dict(seed.raw_payload),
    }


def forwards(apps: Apps, _schema_editor: BaseDatabaseSchemaEditor) -> None:
    from auctions.seed_data import CATALOG_SEED_ITEMS

    catalog_item_model = apps.get_model("auctions", "CatalogItem")
    lot_model = apps.get_model("auctions", "Lot")
    receipt_model = apps.get_model("auctions", "Receipt")

    for seed in CATALOG_SEED_ITEMS:
        legacy_id = next(
            (
                old
                for old, new in _LEGACY_EXTERNAL_IDS.items()
                if new == seed.external_id
            ),
            None,
        )
        old_ids = [seed.external_id]
        if legacy_id is not None:
            old_ids.append(legacy_id)

        for old_id in old_ids:
            catalog_item_model.objects.filter(
                source=seed.source,
                external_id=old_id,
            ).update(**_seed_fields(seed))
            lot_model.objects.filter(
                source=seed.source,
                external_id=old_id,
            ).update(
                external_id=seed.external_id,
                title=seed.title,
                description=seed.description,
                image_url=seed.image_url,
                image_remote_url=seed.image_url,
                image_cached=False,
                source_url=seed.source_url,
                category=seed.category,
                attributes=dict(seed.attributes),
            )
            receipt_model.objects.filter(
                item_source=seed.source,
                item_external_id=old_id,
            ).update(
                item_external_id=seed.external_id,
                item_title=seed.title,
                item_image_url=seed.image_url,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("auctions", "0003_receipt"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
