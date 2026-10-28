"""Verificação pública de históricos e comprovantes."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

from django.conf import settings
from django.utils import timezone

from auctions.models import Bid, Lot, Receipt
from auctions.services.integrity import GENESIS_HASH, bid_hashes, bid_payload

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)
type JSONValue = (
    str | int | float | bool | list[JSONValue] | dict[str, JSONValue] | None
)


class AnchorRecord(TypedDict):
    """Formato persistido por linha no checkpoint externo."""

    lot_id: str
    sequence: int
    head: str
    count: int
    recorded_at: str


class AuditFailure(TypedDict):
    """Falha identificada na sequência de lances."""

    code: str
    sequence: int | None


def _anchor_record(value: JSONValue) -> AnchorRecord | None:
    if not isinstance(value, dict):
        return None
    required = ("lot_id", "sequence", "head", "count", "recorded_at")
    if any(key not in value for key in required):
        return None
    record = cast("AnchorRecord", value)
    if not isinstance(record["lot_id"], str) or not isinstance(
        record["head"], str
    ):
        return None
    if (
        not isinstance(record["sequence"], int)
        or not isinstance(record["count"], int)
        or not isinstance(record["recorded_at"], str)
    ):
        return None
    return record


def write_anchor(lot_id: UUID, sequence: int, head: str, count: int) -> None:
    """Acrescenta checkpoint após o commit, sem comprometer a transação."""
    if not settings.BID_ANCHOR_PATH:
        return
    path = Path(settings.BID_ANCHOR_PATH)
    record: AnchorRecord = {
        "lot_id": str(lot_id),
        "sequence": sequence,
        "head": head,
        "count": count,
        "recorded_at": timezone.now()
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z"),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as anchor_file:
            anchor_file.write(
                json.dumps(record, sort_keys=True, separators=(",", ":"))
                + "\n"
            )
    except OSError:
        logger.exception("Falha ao gravar âncora para lote %s", lot_id)


def _read_anchor(lot_id: UUID) -> AnchorRecord | None:
    if not settings.BID_ANCHOR_PATH:
        return None
    path = Path(settings.BID_ANCHOR_PATH)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    latest: AnchorRecord | None = None
    for line in lines:
        try:
            record = _anchor_record(cast("JSONValue", json.loads(line)))
        except json.JSONDecodeError:
            continue
        if record is not None and record["lot_id"] == str(lot_id):
            latest = record
    return latest


def _anchor_status(lot: Lot) -> tuple[str, bool]:
    record = _read_anchor(lot.pk)
    if record is None:
        return "unavailable", False
    if record["count"] > lot.bids_count or (
        record["count"] == lot.bids_count
        and record["head"] != lot.history_head
    ):
        return "rollback_detected", True
    if record["count"] < lot.bids_count:
        return "behind", False
    return "ok", False


def verify_lot(
    lot: Lot,
) -> dict[
    str,
    bool | str | int | list[AuditFailure] | list[dict[str, str | int]] | None,
]:
    """Valida lances, denormalização e checkpoint externo."""
    bids = list(Bid.objects.filter(lot=lot).order_by("sequence"))
    failures: list[AuditFailure] = []
    previous = GENESIS_HASH
    valid_bid_rows: list[dict[str, str | int]] = []
    for expected, bid in enumerate(bids, start=1):
        payload = bid_payload(bid)
        content_hash, chain_hash = bid_hashes(payload)
        if bid.sequence != expected:
            failures.append({"code": "SEQUENCE_GAP", "sequence": bid.sequence})
        if bid.prev_hash != previous:
            failures.append(
                {"code": "PREV_HASH_MISMATCH", "sequence": bid.sequence}
            )
        if bid.content_hash != content_hash:
            failures.append(
                {"code": "CONTENT_HASH_MISMATCH", "sequence": bid.sequence}
            )
        if bid.hash != chain_hash:
            failures.append(
                {"code": "CHAIN_HASH_MISMATCH", "sequence": bid.sequence}
            )
        previous = bid.hash
        valid_bid_rows.append(
            {
                "sequence": bid.sequence,
                "amount": f"{bid.amount:.2f}",
                "bidder_alias": bid.bidder_alias,
                "placed_at": payload["placed_at"],
                "prev_hash": bid.prev_hash,
                "content_hash": bid.content_hash,
                "hash": bid.hash,
            }
        )
    if len(bids) != lot.bids_count:
        failures.append({"code": "COUNT_MISMATCH", "sequence": None})
    computed_head = previous if bids else ""
    if computed_head != lot.history_head:
        failures.append({"code": "HEAD_MISMATCH", "sequence": None})
    anchor_status, rolled_back = _anchor_status(lot)
    if rolled_back:
        failures.append({"code": "ROLLBACK_DETECTED", "sequence": None})
    return {
        "valid": not failures,
        "head_hash": computed_head,
        "bid_count": len(bids),
        "first_invalid_sequence": failures[0]["sequence"]
        if failures
        else None,
        "failures": failures,
        "anchor_status": anchor_status,
        "bids": valid_bid_rows,
        "limitations": (
            "Verificação HMAC feita pelo backend; não é prova independente. "
            "A âncora no mesmo servidor não protege contra controle "
            "do servidor."
        ),
    }


def _receipt_payload(receipt: Receipt) -> dict[str, str | int]:
    return {
        "token": str(receipt.token),
        "lot_id": str(receipt.lot_id),
        "lot_code": receipt.lot_code,
        "winner_alias": receipt.winner_alias,
        "seller_alias": receipt.seller_alias,
        "item_source": receipt.item_source,
        "item_external_id": receipt.item_external_id,
        "item_title": receipt.item_title,
        "item_image_url": receipt.item_image_url,
        "final_price": f"{receipt.final_price:.2f}",
        "issued_at": receipt.issued_at.isoformat(
            timespec="microseconds"
        ).replace("+00:00", "Z"),
        "audit_head": receipt.audit_head,
        "bid_count": receipt.bid_count,
        "hash_version": receipt.hash_version,
    }


def verify_receipt(receipt: Receipt) -> dict[str, bool | str | int]:
    """Valida HMAC do comprovante e correspondência com a cadeia atual."""
    payload = json.dumps(
        _receipt_payload(receipt),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    expected = hmac.new(
        settings.RECEIPT_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    history = verify_lot(receipt.lot)
    history_valid = bool(history["valid"])
    head_matches = (
        history["head_hash"] == receipt.audit_head
        and history["bid_count"] == receipt.bid_count
    )
    return {
        "receipt_valid": hmac.compare_digest(
            expected, receipt.verification_hash
        ),
        "history_valid": history_valid,
        "head_matches": head_matches,
        "bid_count": receipt.bid_count,
        "anchor_status": str(history["anchor_status"]),
        "limitations": (
            "A assinatura é conferida pelo backend; o comprovante no mesmo "
            "banco não prova ausência de rollback completo."
        ),
    }
