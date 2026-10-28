from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from users.forms import UserChangeForm, UserCreationForm
from users.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin do usuário com email como identificador de login."""

    form = UserChangeForm
    add_form = UserCreationForm

    list_display = (
        "email",
        "public_alias",
        "role",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "public_alias", "full_name")
    ordering = ("-date_joined",)
    readonly_fields = ("id", "public_alias", "date_joined", "last_login")
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Perfil"),
            {"fields": ("role", "public_alias", "full_name")},
        ),
        (_("Identificador"), {"fields": ("id",)}),
        (
            _("Permissões"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Datas"), {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "role",
                    "full_name",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
