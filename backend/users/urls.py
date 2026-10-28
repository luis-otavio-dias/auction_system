"""Rotas de autenticação do app de usuários."""

from django.urls import path

from users.views import (
    CookieLogoutView,
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    MeView,
    RegisterView,
    WsTicketView,
)

app_name = "users"

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("ws-ticket", WsTicketView.as_view(), name="ws_ticket"),
    path(
        "token/",
        CookieTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "refresh/",
        CookieTokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "token/refresh/",
        CookieTokenRefreshView.as_view(),
        name="token_refresh_legacy",
    ),
    path("logout/", CookieLogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
]
