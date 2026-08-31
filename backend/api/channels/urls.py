"""Маршруты раздела каналов продаж. Только пути."""

from django.urls import path

from api.channels import views

urlpatterns = [
    path("", views.channels, name="channels"),
    path("xlsx/", views.channels_xlsx, name="channels-xlsx"),
]
