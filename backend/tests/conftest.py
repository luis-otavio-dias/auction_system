"""Shared fixtures for the test suite."""

import pytest

from users.models import User
from wallet.models import Wallet

TEST_PASSWORD = "test-password-123"


@pytest.fixture
def seller() -> User:
    """Create a seller user; the wallet is created by the signal."""
    return User.objects.create_user(
        email="seller@example.com",
        password=TEST_PASSWORD,
        role="SELLER",
        full_name="Seller Example",
    )


@pytest.fixture
def bidder() -> User:
    """Create a bidder user; the wallet is created by the signal."""
    return User.objects.create_user(
        email="bidder@example.com",
        password=TEST_PASSWORD,
        role="BIDDER",
        full_name="Bidder Example",
    )


@pytest.fixture
def wallet(bidder: User) -> Wallet:
    """Return the wallet automatically created for the bidder."""
    return Wallet.objects.get(user=bidder)
