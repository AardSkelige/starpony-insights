"""Маршруты API. Только пути — ни строчки логики."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("auth/", include("api.auth.urls")),
    path("channels/", include("api.channels.urls")),
    path("deadlines/", include("api.deadlines.urls")),
    path("shipments/", include("api.shipments.urls")),
    path("supplies/", include("api.supplies.urls")),
    path("suppliers/", include("api.suppliers.urls")),
    path("sync/", include("api.sync.urls")),
    # Схема — источник типов фронтенда: `npm run api:types` берёт её отсюда.
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    # Страница для человека: посмотреть, что API отдаёт, и попробовать запрос
    # прямо в браузере. Закрыта входом, как и всё остальное.
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]
