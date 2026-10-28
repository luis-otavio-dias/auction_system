"""Serializers do app de usuários."""

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from users.models import User


class UserMeSerializer(serializers.ModelSerializer[User]):
    """Dados privados do próprio usuário autenticado."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "role",
            "public_alias",
            "full_name",
            "is_active",
        )
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer[User]):
    """Entrada pública para criar conta de leiloeiro ou licitante."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        trim_whitespace=False,
    )
    role = serializers.ChoiceField(choices=User.Role.choices)
    public_alias = serializers.CharField(
        max_length=24,
        required=False,
        allow_blank=True,
        validators=(UniqueValidator(queryset=User.objects.all()),),
    )

    def create(self, validated_data: dict[str, str]) -> User:
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            role=validated_data["role"],
        )
        alias = validated_data.get("public_alias", "").strip()
        if alias:
            user.public_alias = alias
            user.save(update_fields=("public_alias",))
        return user
