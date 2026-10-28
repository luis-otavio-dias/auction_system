"""Rotas REST do app de carteira."""

from django.urls import path

from wallet.views import WalletDepositView, WalletTransactionsView, WalletView

app_name = "wallet"

urlpatterns = [
    path("wallet", WalletView.as_view(), name="wallet"),
    path(
        "wallet/deposits", WalletDepositView.as_view(), name="wallet_deposits"
    ),
    path(
        "wallet/transactions",
        WalletTransactionsView.as_view(),
        name="wallet_transactions",
    ),
]
