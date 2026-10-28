"""Canonicalização e verificação dos hashes de lances."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING, TypedDict

from django.conf import settings

if TYPE_CHECKING:
    from auctions.models import Bid

GENESIS_HASH = "0" * 64


class BidPayload(TypedDict):
    """Payload estável que participa da cadeia de integridade."""

    lot_id: str
    sequence: int
    bidder_id: str
    bidder_alias: str
    amount: str
    placed_at: str
    ends_at_before: str
    ends_at_after: str
    prev_hash: str
    hash_version: int


def canonical_json(payload: BidPayload) -> str:
    """Serializa o payload com chaves ordenadas e separadores fixos."""
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def bid_payload(bid: Bid) -> BidPayload:
    """Monta o payload com snapshots armazenados no lance."""
    return {
        "lot_id": str(bid.lot_id),
        "sequence": bid.sequence,
        "bidder_id": str(bid.bidder_id),
        "bidder_alias": bid.bidder_alias,
        "amount": f"{bid.amount:.2f}",
        "placed_at": bid.placed_at.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "ends_at_before": bid.ends_at_before.isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
        "ends_at_after": bid.ends_at_after.isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
        "prev_hash": bid.prev_hash,
        "hash_version": bid.hash_version,
    }


def bid_hashes(payload: BidPayload) -> tuple[str, str]:
    """Calcula content hash e HMAC encadeado."""
    content_hash = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
    chain_hash = hmac.new(
        settings.BID_HISTORY_SECRET.encode(),
        f"{payload['prev_hash']}:{content_hash}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return content_hash, chain_hash
