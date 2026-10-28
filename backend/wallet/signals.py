"""Signals do app de carteira."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from wallet.models import Wallet

if TYPE_CHECKING:
    from django.db.models import Model


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_wallet_for_user(
    sender: type[Model],
    instance: Model,
    *,
    created: bool,
    **_kwargs: bool | str | frozenset[str] | None,
) -> None:
    """Garante uma carteira para cada usuário recém-criado."""
    del sender
    if created:
        Wallet.objects.get_or_create(user_id=instance.pk)
