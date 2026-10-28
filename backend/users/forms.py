from __future__ import annotations

from django.contrib.auth.forms import (
    BaseUserCreationForm,
)
from django.contrib.auth.forms import (
    UserChangeForm as BaseUserChangeForm,
)

from users.models import User


class UserCreationForm(BaseUserCreationForm):
    """Formulário de criação de usuário no Django Admin."""

    class Meta:
        model = User
        fields = ("email", "role", "full_name")


class UserChangeForm(BaseUserChangeForm):
    """Formulário de alteração de usuário no Django Admin."""

    class Meta:
        model = User
        fields = "__all__"
