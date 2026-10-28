from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from users.models import User


class UserManager(BaseUserManager["User"]):
    """Manager do usuário cujo login é o email."""

    use_in_migrations = True

    def create_user(
        self,
        email: str,
        password: str | None = None,
        *,
        role: str,
        full_name: str = "",
    ) -> User:
        """Cria e persiste um usuário comum."""
        normalized_email = self.normalize_email(email).lower()
        if not normalized_email:
            message = "O email é obrigatório."
            raise ValueError(message)

        user = self.model(
            email=normalized_email,
            role=role,
            full_name=full_name,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        *,
        role: str = "SELLER",
        full_name: str = "",
    ) -> User:
        """Cria um superusuário para acesso ao Django Admin."""
        user = self.create_user(
            email,
            password,
            role=role,
            full_name=full_name,
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(
            using=self._db,
            update_fields=("is_staff", "is_superuser"),
        )
        return user
