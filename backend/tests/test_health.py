from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from django.test import Client


EXPECTED_STATUS = HTTPStatus.OK


@pytest.mark.django_db
def test_health_status(client: Client) -> None:
    response = client.get("/health/")
    assert response.status_code == EXPECTED_STATUS
