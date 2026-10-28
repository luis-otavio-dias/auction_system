"""Permissões de leitura e operações da carteira."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission

from users.models import User

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class IsBidder(BasePermission):
    """Restringe operações financeiras de licitação ao papel BIDDER."""

    message = "Apenas licitantes podem usar esta operação."

    def has_permission(self, request: Request, _view: APIView) -> bool:
        user = request.user
        return (
            isinstance(user, User) and user.is_authenticated and user.is_bidder
        )
