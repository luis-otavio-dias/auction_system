from __future__ import annotations

import secrets
import uuid
from typing import TYPE_CHECKING, ClassVar, override

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from users.managers import UserManager

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.db.models.base import ModelBase


class User(AbstractBaseUser, PermissionsMixin):
    """Usuário autenticado por email e identificado publicamente por alias."""

    class Role(models.TextChoices):
        SELLER = "SELLER", _("Leiloeiro")
        BIDDER = "BIDDER", _("Licitante")

    ALIAS_PREFIXES: ClassVar[dict[str, str]] = {
        Role.SELLER: "Leiloeiro",
        Role.BIDDER: "Licitante",
    }
    ALIAS_SUFFIX_BYTES = 3

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    email = models.EmailField(_("email"), unique=True)
    role = models.CharField(
        _("perfil"),
        max_length=16,
        choices=Role.choices,
        db_index=True,
    )
    public_alias = models.CharField(
        _("alias público"),
        max_length=24,
        unique=True,
        editable=False,
    )
    full_name = models.CharField(
        _("nome completo"),
        max_length=150,
        blank=True,
    )
    is_active = models.BooleanField(_("ativo"), default=True)
    is_staff = models.BooleanField(_("membro da equipe"), default=False)
    date_joined = models.DateTimeField(
        _("data de cadastro"),
        default=timezone.now,
    )

    objects: ClassVar[UserManager] = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    class Meta:
        verbose_name = _("usuário")
        verbose_name_plural = _("usuários")
        ordering = ("-date_joined",)
        indexes = (
            models.Index(
                fields=("date_joined",),
                name="users_user_date_joined_idx",
            ),
        )

    def _build_public_alias(self) -> str:
        prefix = self.ALIAS_PREFIXES.get(self.role)
        if prefix is None:
            message = f"Perfil inválido para geração de alias: {self.role!r}."
            raise ValueError(message)
        suffix = secrets.token_hex(self.ALIAS_SUFFIX_BYTES).upper()
        return f"{prefix}-{suffix}"

    def _generate_unique_public_alias(self) -> str:
        while True:
            alias = self._build_public_alias()
            if not type(self).objects.filter(public_alias=alias).exists():
                return alias

    @override
    def save(
        self,
        *,
        force_insert: bool | tuple[ModelBase, ...] = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        self.email = self.email.strip().lower()
        if not self.public_alias:
            self.public_alias = self._generate_unique_public_alias()
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @property
    def is_seller(self) -> bool:
        return self.role == self.Role.SELLER

    @property
    def is_bidder(self) -> bool:
        return self.role == self.Role.BIDDER

    def get_full_name(self) -> str:
        return self.full_name or self.public_alias

    def get_short_name(self) -> str:
        return self.public_alias

    @override
    def __str__(self) -> str:
        return self.email
