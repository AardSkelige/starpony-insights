"""Маршруты синхронизации. Только пути."""

from django.urls import path

from api.sync import views

urlpatterns = [
    path("refresh/", views.refresh, name="sync-refresh"),
]
