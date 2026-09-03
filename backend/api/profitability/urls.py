"""Маршруты раздела «Прибыльность». Только пути."""

from django.urls import path

from api.profitability import views

urlpatterns = [
    path("", views.profitability, name="profitability"),
    path("xlsx/", views.profitability_xlsx, name="profitability-xlsx"),
]
