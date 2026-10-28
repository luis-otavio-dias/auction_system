"""Configuração do app de carteira."""

import importlib

from django.apps import AppConfig


class WalletConfig(AppConfig):
    """Configura o app ``wallet`` e carrega seus signals."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "wallet"
    verbose_name = "Carteira"

    def ready(self) -> None:
        """Registra os handlers de signal do app."""
        importlib.import_module("wallet.signals")
