"""Permissões do app de leilões."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission

from users.models import User

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView


class IsSeller(BasePermission):
    """Permite acesso apenas a usuários autenticados com papel de leiloeiro."""

    message = "Apenas leiloeiros podem executar esta ação."

    def has_permission(self, request: Request, _view: APIView) -> bool:
        user = request.user
        return (
            isinstance(user, User) and user.is_authenticated and user.is_seller
        )


class IsBidder(BasePermission):
    """Permite acesso apenas a usuários autenticados com papel BIDDER."""

    message = "Apenas licitantes podem executar esta ação."

    def has_permission(self, request: Request, _view: APIView) -> bool:
        user = request.user
        return (
            isinstance(user, User) and user.is_authenticated and user.is_bidder
        )
