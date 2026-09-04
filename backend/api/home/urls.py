"""Маршруты главной. Только пути."""

from django.urls import path

from api.home import views

urlpatterns = [
    path("", views.home, name="home"),
]
