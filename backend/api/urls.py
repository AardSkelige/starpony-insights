"""Маршруты API. Только пути — ни строчки логики."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    path("auth/", include("api.auth.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]
