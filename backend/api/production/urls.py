"""Маршруты «Расчёта производства». Только пути."""

from django.urls import path

from api.production import views

urlpatterns = [
    path("products/", views.products, name="production-products"),
    path("batch/", views.batch, name="production-batch"),
]
