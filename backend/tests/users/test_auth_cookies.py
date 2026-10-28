"""Tests for cookie-based JWT authentication."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from django.conf import settings

from users.models import User

if TYPE_CHECKING:
    from django.test import Client


pytestmark = pytest.mark.django_db

TEST_PASSWORD = "test-password-123"
LOGIN_URL = "/api/auth/token/"
REFRESH_URL = "/api/auth/refresh/"
LOGOUT_URL = "/api/auth/logout/"
ME_URL = "/api/auth/me/"


@pytest.fixture(autouse=True)
def cookie_settings(settings) -> None:
    """Keep test cookies usable over the test client's HTTP requests."""
    settings.AUTH_COOKIE_SECURE = False
    settings.AUTH_COOKIE_SAMESITE = "Lax"
    settings.AUTH_COOKIE_DOMAIN = None


def login(client: Client, user: User) -> None:
    response = client.post(
        LOGIN_URL,
        data={"email": user.email, "password": TEST_PASSWORD},
        content_type="application/json",
    )
    assert response.status_code == HTTPStatus.OK


def test_login_sets_httponly_cookies(client: Client, bidder: User) -> None:
    response = client.post(
        LOGIN_URL,
        data={"email": bidder.email, "password": TEST_PASSWORD},
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()) == {"detail"}

    access = response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]
    refresh = response.cookies[settings.AUTH_COOKIE_REFRESH_NAME]

    assert access.value
    assert bool(access["httponly"]) is True
    assert access["path"] == settings.AUTH_COOKIE_ACCESS_PATH
    assert access["samesite"] == settings.AUTH_COOKIE_SAMESITE
    assert int(access["max-age"]) == settings.AUTH_COOKIE_ACCESS_MAX_AGE

    assert refresh.value
    assert bool(refresh["httponly"]) is True
    assert refresh["path"] == settings.AUTH_COOKIE_REFRESH_PATH
    assert refresh["samesite"] == settings.AUTH_COOKIE_SAMESITE
    assert int(refresh["max-age"]) == settings.AUTH_COOKIE_REFRESH_MAX_AGE


def test_public_registration_creates_bidder_with_optional_alias(
    client: Client,
) -> None:
    response = client.post(
        "/api/auth/register",
        data={
            "email": "new-bidder@example.com",
            "password": "new-password-123",
            "role": "BIDDER",
            "public_alias": "Licitante Novo",
        },
        content_type="application/json",
    )

    assert response.status_code == HTTPStatus.CREATED
    user = User.objects.get(email="new-bidder@example.com")
    assert user.role == User.Role.BIDDER
    assert user.public_alias == "Licitante Novo"


def test_me_uses_access_cookie(client: Client, bidder: User) -> None:
    login(client, bidder)

    response = client.get(ME_URL)

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["email"] == bidder.email
    assert payload["role"] == "BIDDER"
    assert payload["public_alias"] == bidder.public_alias
    assert "access" not in payload
    assert "refresh" not in payload


def test_me_rejects_missing_or_invalid_cookie(
    client: Client,
) -> None:
    response = client.get(ME_URL)
    assert response.status_code == HTTPStatus.UNAUTHORIZED

    client.cookies[settings.AUTH_COOKIE_ACCESS_NAME] = "invalid-token"

    response = client.get(ME_URL)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


def test_me_accepts_bearer_header_as_fallback(
    client: Client,
    bidder: User,
) -> None:
    login(client, bidder)
    access = client.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    client.cookies.clear()

    response = client.get(
        ME_URL,
        HTTP_AUTHORIZATION=f"Bearer {access}",
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["email"] == bidder.email


def test_refresh_uses_refresh_cookie_and_rotates_access(
    client: Client,
    bidder: User,
) -> None:
    login(client, bidder)
    old_access = client.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    old_refresh = client.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    response = client.post(REFRESH_URL)

    assert response.status_code == HTTPStatus.OK
    assert set(response.json()) == {"detail"}
    new_access = response.cookies[settings.AUTH_COOKIE_ACCESS_NAME].value
    assert new_access
    assert new_access != old_access
    assert settings.AUTH_COOKIE_REFRESH_NAME in response.cookies

    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = old_refresh
    replay = client.post(REFRESH_URL)

    assert replay.status_code == HTTPStatus.UNAUTHORIZED


def test_refresh_requires_refresh_cookie(
    client: Client,
    bidder: User,
) -> None:
    login(client, bidder)
    client.cookies.pop(settings.AUTH_COOKIE_REFRESH_NAME, None)

    response = client.post(REFRESH_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Refresh token não encontrado."


def test_refresh_rejects_invalid_refresh_cookie(
    client: Client,
    bidder: User,
) -> None:
    login(client, bidder)
    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = "invalid-refresh"

    response = client.post(REFRESH_URL)

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Refresh token inválido ou expirado."
    assert (
        int(
            response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]["max-age"],
        )
        == 0
    )


def test_logout_clears_and_blacklists_auth_cookies(
    client: Client,
    bidder: User,
) -> None:
    login(client, bidder)
    refresh = client.cookies[settings.AUTH_COOKIE_REFRESH_NAME].value

    response = client.post(LOGOUT_URL)

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert (
        int(
            response.cookies[settings.AUTH_COOKIE_ACCESS_NAME]["max-age"],
        )
        == 0
    )
    assert (
        int(
            response.cookies[settings.AUTH_COOKIE_REFRESH_NAME]["max-age"],
        )
        == 0
    )

    client.cookies[settings.AUTH_COOKIE_REFRESH_NAME] = refresh
    replay = client.post(REFRESH_URL)

    assert replay.status_code == HTTPStatus.UNAUTHORIZED
