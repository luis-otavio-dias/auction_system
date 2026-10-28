"""Testes dos endpoints HTTP da carteira."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from wallet.models import Wallet, WalletTransaction

if TYPE_CHECKING:
    from django.test import Client

    from users.models import User

pytestmark = pytest.mark.django_db


def test_wallet_read_deposit_and_transaction_history(
    client: Client, bidder: User
) -> None:
    login_user(client, bidder)

    wallet_response = client.get("/api/wallet")
    assert wallet_response.status_code == HTTPStatus.OK
    assert wallet_response.json()["available"] == "0.00"

    deposit_response = client.post(
        "/api/wallet/deposits",
        data={"amount": "250.00", "idempotency_key": "deposit-1"},
        content_type="application/json",
    )
    assert deposit_response.status_code == HTTPStatus.CREATED
    assert deposit_response.json()["balance"] == "250.00"
    assert deposit_response.json()["available"] == "250.00"

    history_response = client.get("/api/wallet/transactions")
    assert history_response.status_code == HTTPStatus.OK
    row = history_response.json()["results"][0]
    assert row["type"] == WalletTransaction.Type.DEPOSIT
    assert row["amount"] == "250.00"
    assert "email" not in row
    assert Wallet.objects.get(user=bidder).balance == 250


def test_seller_wallet_permissions(client: Client, seller: User) -> None:
    login_user(client, seller)

    wallet_response = client.get("/api/wallet")
    transactions_response = client.get("/api/wallet/transactions")
    wallet_post = client.post(
        "/api/wallet",
        data={"amount": "50.00"},
        content_type="application/json",
    )
    deposit_response = client.post(
        "/api/wallet/deposits",
        data={"amount": "50.00"},
        content_type="application/json",
    )
    assert wallet_response.status_code == HTTPStatus.OK
    assert transactions_response.status_code == HTTPStatus.OK
    assert wallet_post.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert deposit_response.status_code == HTTPStatus.FORBIDDEN


def test_wallet_endpoints_require_authentication(client: Client) -> None:
    assert client.get("/api/wallet").status_code == HTTPStatus.UNAUTHORIZED
    assert (
        client.get("/api/wallet/transactions").status_code
        == HTTPStatus.UNAUTHORIZED
    )


def test_deposit_is_idempotent_and_reused_key_conflicts(
    client: Client, bidder: User
) -> None:
    login_user(client, bidder)

    first = client.post(
        "/api/wallet/deposits",
        data={"amount": "100.00", "idempotency_key": "same-key"},
        content_type="application/json",
    )
    replay = client.post(
        "/api/wallet/deposits",
        data={"amount": "100.00", "idempotency_key": "same-key"},
        content_type="application/json",
    )
    conflict = client.post(
        "/api/wallet/deposits",
        data={"amount": "120.00", "idempotency_key": "same-key"},
        content_type="application/json",
    )

    assert first.status_code == HTTPStatus.CREATED
    assert replay.status_code == HTTPStatus.OK
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert replay.json()["balance"] == "100.00"
    assert conflict.status_code == HTTPStatus.CONFLICT
    assert conflict.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert (
        WalletTransaction.objects.filter(
            wallet__user=bidder,
            type=WalletTransaction.Type.DEPOSIT,
        ).count()
        == 1
    )


def login_user(client: Client, user: User) -> None:
    response = client.post(
        "/api/auth/token/",
        data={"email": user.email, "password": "test-password-123"},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.OK
