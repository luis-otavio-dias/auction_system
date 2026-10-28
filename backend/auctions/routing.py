"""Rotas dos canais WebSocket."""

from django.urls import path

from auctions.consumers import LotConsumer, NotificationConsumer

websocket_urlpatterns = [
    path("ws/lots/<uuid:lot_id>/", LotConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]
