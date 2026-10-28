"""Rotas do app de leilões."""

from django.urls import path

from auctions.views import (
    CatalogItemDetailView,
    CatalogSearchView,
    LotAuditView,
    LotBidsView,
    LotCancelView,
    LotDetailView,
    LotListView,
    MyBidsView,
    MyWinsView,
    ReceiptDetailView,
    ReceiptVerifyView,
    SellerLotsView,
    SellerSummaryView,
)

app_name = "auctions"

urlpatterns = [
    path("me/bids", MyBidsView.as_view(), name="my_bids"),
    path("me/wins", MyWinsView.as_view(), name="my_wins"),
    path("seller/lots", SellerLotsView.as_view(), name="seller_lots"),
    path("seller/summary", SellerSummaryView.as_view(), name="seller_summary"),
    path(
        "receipts/<uuid:token>",
        ReceiptDetailView.as_view(),
        name="receipt_detail",
    ),
    path(
        "receipts/<uuid:token>/verify",
        ReceiptVerifyView.as_view(),
        name="receipt_verify",
    ),
    path(
        "catalog/search",
        CatalogSearchView.as_view(),
        name="catalog_search",
    ),
    path(
        "catalog/items/<uuid:item_id>",
        CatalogItemDetailView.as_view(),
        name="catalog_item_detail",
    ),
    path("lots", LotListView.as_view(), name="lot_list"),
    path("lots/<uuid:lot_id>", LotDetailView.as_view(), name="lot_detail"),
    path("lots/<uuid:lot_id>/bids", LotBidsView.as_view(), name="lot_bids"),
    path("lots/<uuid:lot_id>/audit", LotAuditView.as_view(), name="lot_audit"),
    path(
        "lots/<uuid:lot_id>/cancel",
        LotCancelView.as_view(),
        name="lot_cancel",
    ),
]
