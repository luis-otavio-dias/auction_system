"""Tests for the custom user model and its manager."""

import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from users.models import User

ALIAS_SUFFIX_PATTERN = re.compile(r"[0-9A-F]{6}")


@pytest.mark.django_db
def test_create_user_normalizes_email_to_lowercase() -> None:
    user = User.objects.create_user(
        email="Mixed.Case@Example.COM",
        password="secret",
        role="BIDDER",
    )

    assert user.email == "mixed.case@example.com"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "prefix"),
    [("SELLER", "Leiloeiro-"), ("BIDDER", "Licitante-")],
)
def test_public_alias_uses_role_prefix(role: str, prefix: str) -> None:
    user = User.objects.create_user(
        email=f"{role.lower()}@example.com",
        password="secret",
        role=role,
    )

    assert user.public_alias.startswith(prefix)
    suffix = user.public_alias.removeprefix(prefix)
    assert ALIAS_SUFFIX_PATTERN.fullmatch(suffix)


@pytest.mark.django_db
def test_public_alias_is_unique() -> None:
    first = User.objects.create_user(
        email="first@example.com",
        password="secret",
        role="BIDDER",
    )
    second = User.objects.create_user(
        email="second@example.com",
        password="secret",
        role="BIDDER",
    )

    assert first.public_alias != second.public_alias
    with transaction.atomic(), pytest.raises(IntegrityError):
        User.objects.filter(pk=second.pk).update(
            public_alias=first.public_alias,
        )


@pytest.mark.django_db
def test_create_seller() -> None:
    user = User.objects.create_user(
        email="seller@example.com",
        password="secret",
        role="SELLER",
        full_name="Seller Example",
    )

    assert user.role == "SELLER"
    assert user.full_name == "Seller Example"


@pytest.mark.django_db
def test_create_bidder() -> None:
    user = User.objects.create_user(
        email="bidder@example.com",
        password="secret",
        role="BIDDER",
        full_name="Bidder Example",
    )

    assert user.role == "BIDDER"
    assert user.full_name == "Bidder Example"


@pytest.mark.django_db
def test_role_helpers(seller: User, bidder: User) -> None:
    assert seller.is_seller
    assert not seller.is_bidder
    assert bidder.is_bidder
    assert not bidder.is_seller


@pytest.mark.django_db
def test_get_full_name_and_short_name() -> None:
    user = User.objects.create_user(
        email="ada@example.com",
        password="secret",
        role="BIDDER",
        full_name="Ada Lovelace",
    )

    assert user.get_full_name() == "Ada Lovelace"
    assert user.get_short_name() == user.public_alias


@pytest.mark.django_db
def test_create_superuser_sets_admin_flags() -> None:
    admin = User.objects.create_superuser(
        email="admin@example.com",
        password="secret",
    )

    assert admin.is_staff
    assert admin.is_superuser
    assert admin.is_active
    assert admin.role == "SELLER"


@pytest.mark.django_db
def test_duplicate_email_is_rejected() -> None:
    email = "duplicate@example.com"
    User.objects.create_user(email=email, password="secret", role="BIDDER")

    expected_errors = (IntegrityError, ValidationError)
    with transaction.atomic(), pytest.raises(expected_errors):
        User.objects.create_user(
            email=email,
            password="another-secret",
            role="SELLER",
        )

    assert User.objects.filter(email=email).count() == 1
