"""Маршруты раздела отгрузок. Только пути."""

from django.urls import path

from api.shipments import views

urlpatterns = [
    path("products/", views.shipment_products, name="shipment-products"),
    path("products/xlsx/", views.shipment_products_xlsx, name="shipment-products-xlsx"),
    path(
        "products/<int:product_id>/",
        views.shipment_product_detail,
        name="shipment-product-detail",
    ),
]
