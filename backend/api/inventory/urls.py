"""Маршруты раздела «Инвентаризация». Только пути."""

from django.urls import path

from api.inventory import views

urlpatterns = [
    path("", views.inventory, name="inventory"),
    path("xlsx/", views.inventory_xlsx, name="inventory-xlsx"),
]
