"""Testes de integridade do histórico e da âncora externa."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from django.test import override_settings
from django.utils import timezone

from auctions.models import Bid, Lot, Receipt
from auctions.services.audit import verify_lot, verify_receipt, write_anchor
from auctions.services.bidding import place_bid
from auctions.services.settlement import settle_lot
from users.models import User
from wallet.models import Wallet

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.django_db


def fund(user: User) -> None:
    wallet = Wallet.objects.get(user=user)
    wallet.balance = Decimal("10000.00")
    wallet.save(update_fields=("balance",))


def test_valid_history_has_public_alias_without_user_id(lot, bidder) -> None:
    fund(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    lot.refresh_from_db()

    result = verify_lot(lot)

    assert result["valid"] is True
    assert result["bid_count"] == 1
    bids = result["bids"]
    assert isinstance(bids, list)
    assert "bidder_alias" in bids[0]
    assert "bidder_id" not in bids[0]


@override_settings(BID_ANCHOR_PATH="")
def test_intermediate_bid_tampering_does_not_cascade_to_later_bids(
    lot, bidder
) -> None:
    second = User.objects.create_user(
        email="audit-second@example.com", password="pass-123456", role="BIDDER"
    )
    third = User.objects.create_user(
        email="audit-third@example.com", password="pass-123456", role="BIDDER"
    )
    for user in (bidder, second, third):
        fund(user)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    middle = place_bid(lot_id=lot.pk, bidder=second, amount=Decimal("1100.00"))
    place_bid(lot_id=lot.pk, bidder=third, amount=Decimal("1200.00"))
    Bid.objects.filter(pk=middle.pk).update(amount=Decimal("1101.00"))
    lot.refresh_from_db()

    failures = verify_lot(lot)["failures"]
    assert isinstance(failures, list)
    assert failures
    assert {failure["sequence"] for failure in failures} == {2}


def test_public_audit_and_receipt_endpoints_have_no_pii(
    client, lot, bidder, seller
) -> None:
    fund(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    lot.ends_at = timezone.now()
    lot.save(update_fields=("ends_at",))
    receipt = settle_lot(lot.pk)
    assert receipt is not None

    audit_response = client.get(f"/api/lots/{lot.pk}/audit")
    receipt_response = client.get(f"/api/receipts/{receipt.token}")
    verify_response = client.get(f"/api/receipts/{receipt.token}/verify")

    assert audit_response.status_code == 200
    assert audit_response.json()["valid"] is True
    assert receipt_response.status_code == 200
    receipt_body = receipt_response.json()
    assert receipt_body["issued_at"]
    assert receipt_body["share_url"].endswith(f"/comprovantes/{receipt.token}")
    assert verify_response.status_code == 200
    public_body = str(audit_response.json()) + str(receipt_response.json())
    assert bidder.email not in public_body
    assert seller.email not in public_body
    assert str(bidder.pk) not in public_body
    assert str(seller.pk) not in public_body


@pytest.mark.parametrize("mutation", ["update", "delete", "insert", "reorder"])
def test_database_tampering_is_detected(lot, bidder, mutation: str) -> None:
    fund(bidder)
    first = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    if mutation in {"delete", "reorder"}:
        other = User.objects.create_user(
            email="audit-other@example.com",
            password="pass-123456",
            role="BIDDER",
        )
        fund(other)
        place_bid(lot_id=lot.pk, bidder=other, amount=Decimal("1100.00"))
    if mutation == "update":
        Bid.objects.filter(pk=first.pk).update(amount=Decimal("1001.00"))
    elif mutation == "delete":
        Bid.objects.filter(pk=first.pk).delete()
    elif mutation == "insert":
        Bid.objects.create(
            lot=lot,
            bidder=bidder,
            bidder_alias=bidder.public_alias,
            sequence=2,
            amount=Decimal("1100.00"),
            placed_at=timezone.now(),
            prev_hash=first.hash,
            content_hash="f" * 64,
            hash="e" * 64,
            ends_at_before=lot.ends_at,
            ends_at_after=lot.ends_at,
        )
    else:
        Bid.objects.filter(pk=first.pk).update(sequence=3)
    lot.refresh_from_db()

    assert verify_lot(lot)["valid"] is False


def test_missing_and_delayed_anchor_are_not_integrity_failures(
    lot, bidder, tmp_path: Path
) -> None:
    fund(bidder)
    bid = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    lot.refresh_from_db()
    anchor_file = tmp_path / "anchors.jsonl"
    with override_settings(BID_ANCHOR_PATH=str(anchor_file)):
        missing = verify_lot(lot)
        anchor_file.write_text(
            json.dumps(
                {
                    "lot_id": str(lot.pk),
                    "sequence": 0,
                    "head": "",
                    "count": 0,
                    "recorded_at": "now",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        delayed = verify_lot(lot)

    assert missing["anchor_status"] == "unavailable"
    assert missing["valid"] is True
    assert delayed["anchor_status"] == "behind"
    assert delayed["valid"] is True
    assert bid.sequence == 1


def test_anchor_ahead_detects_rollback(lot, bidder, tmp_path: Path) -> None:
    fund(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    lot.refresh_from_db()
    anchor_file = tmp_path / "anchors.jsonl"
    anchor_file.write_text(
        json.dumps(
            {
                "lot_id": str(lot.pk),
                "sequence": 2,
                "head": lot.history_head,
                "count": 2,
                "recorded_at": "now",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with override_settings(BID_ANCHOR_PATH=str(anchor_file)):
        result = verify_lot(lot)

    assert result["valid"] is False
    assert result["anchor_status"] == "rollback_detected"
    failures = result["failures"]
    assert isinstance(failures, list)
    assert any(failure["code"] == "ROLLBACK_DETECTED" for failure in failures)


def test_anchor_records_each_committed_bid(
    lot, bidder, tmp_path: Path
) -> None:
    fund(bidder)
    anchor_file = tmp_path / "anchors.jsonl"
    first = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    other = User.objects.create_user(
        email="anchor-other@example.com",
        password="pass-123456",
        role="BIDDER",
    )
    fund(other)
    second = place_bid(lot_id=lot.pk, bidder=other, amount=Decimal("1100.00"))
    lot.refresh_from_db()
    with override_settings(BID_ANCHOR_PATH=str(anchor_file)):
        write_anchor(lot.pk, 1, first.hash, 1)
        write_anchor(lot.pk, 2, second.hash, 2)

    records = [
        json.loads(line) for line in anchor_file.read_text().splitlines()
    ]
    assert [record["sequence"] for record in records] == [1, 2]
    assert all(record["lot_id"] == str(lot.pk) for record in records)
    assert records[0]["head"] == first.hash
    assert records[1]["head"] == second.hash


@pytest.mark.parametrize(
    ("tampering", "expected_failure"),
    [
        ("count", "COUNT_MISMATCH"),
        ("head", "HEAD_MISMATCH"),
        ("sequence", "SEQUENCE_GAP"),
        ("prev", "PREV_HASH_MISMATCH"),
        ("content", "CONTENT_HASH_MISMATCH"),
        ("chain", "CHAIN_HASH_MISMATCH"),
    ],
)
def test_audit_reports_specific_consistency_failures(
    lot, bidder, tampering: str, expected_failure: str
) -> None:
    fund(bidder)
    bid = place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    if tampering == "count":
        Lot.objects.filter(pk=lot.pk).update(bids_count=2)
    elif tampering == "head":
        lot.history_head = "f" * 64
        lot.save(update_fields=("history_head",))
    elif tampering == "sequence":
        Bid.objects.filter(pk=bid.pk).update(sequence=2)
    elif tampering == "prev":
        Bid.objects.filter(pk=bid.pk).update(prev_hash="f" * 64)
    elif tampering == "content":
        Bid.objects.filter(pk=bid.pk).update(content_hash="f" * 64)
    else:
        Bid.objects.filter(pk=bid.pk).update(hash="f" * 64)

    result = verify_lot(lot)

    assert result["valid"] is False
    failures = result["failures"]
    assert isinstance(failures, list)
    assert any(failure["code"] == expected_failure for failure in failures)


def test_receipt_hmac_detects_snapshot_tampering(lot, bidder) -> None:
    fund(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    lot.ends_at = timezone.now()
    lot.save(update_fields=("ends_at",))
    receipt = settle_lot(lot.pk)
    assert receipt is not None
    assert verify_receipt(receipt)["receipt_valid"] is True


def test_wins_and_seller_summary_include_settlement_details(
    client, lot, bidder, seller, login
) -> None:
    fund(bidder)
    place_bid(lot_id=lot.pk, bidder=bidder, amount=Decimal("1000.00"))
    lot.ends_at = timezone.now()
    lot.save(update_fields=("ends_at",))
    receipt = settle_lot(lot.pk)
    assert receipt is not None

    login(bidder)
    wins = client.get("/api/me/wins")
    assert wins.status_code == 200
    win = wins.json()[0]
    assert win["issued_at"]
    assert win["share_url"].endswith(f"/comprovantes/{receipt.token}")

    login(seller)
    summary = client.get("/api/seller/summary")
    assert summary.status_code == 200
    payload = summary.json()
    assert payload["total_received"] == "1000.00"
    assert payload["results_by_lot"][0] == {
        "lot_id": str(lot.pk),
        "code": lot.code,
        "title": lot.title,
        "final_price": "1000.00",
        "winner_alias": bidder.public_alias,
        "settled_at": payload["results_by_lot"][0]["settled_at"],
    }
    assert payload["unsold_lots"] == []
    assert payload["blocked_lots"] == []

    Receipt.objects.filter(pk=receipt.pk).update(
        final_price=Decimal("1200.00")
    )
    receipt.refresh_from_db()

    result = verify_receipt(receipt)
    assert result["receipt_valid"] is False
    assert result["history_valid"] is True
    assert result["head_matches"] is True
