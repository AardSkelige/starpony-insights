"""Маршруты раздела поставщиков. Только пути."""

from django.urls import path

from api.suppliers import views

urlpatterns = [
    path("", views.suppliers, name="suppliers"),
    path("xlsx/", views.suppliers_xlsx, name="suppliers-xlsx"),
]
