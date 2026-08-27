"""Кнопка «Обновить». View тонкий: позвать сервис и сериализовать."""

from drf_spectacular.utils import extend_schema
from rest_framework import status as http
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.sync import services
from api.sync.serializers import RefusedSerializer, SyncRunSerializer


@extend_schema(
    request=None,
    responses={200: SyncRunSerializer, 429: RefusedSerializer, 409: RefusedSerializer},
    summary="Обновить данные из МойСклада",
    description=(
        "Единственное место, где запрос человека доходит до МойСклада. "
        "Ограничено паузой между запусками и блокировкой: корзина лимита "
        "общая с ботом, который проверяет учёт круглосуточно."
    ),
)
@api_view(["POST"])
def refresh(request):
    try:
        run = services.refresh()
    except services.Refused as refusal:
        # 429 — «слишком часто», 409 — «сейчас нельзя по другой причине».
        # Разные коды нужны фронту: первый стоит показать с обратным отсчётом,
        # второй — просто текстом.
        code = http.HTTP_429_TOO_MANY_REQUESTS if refusal.retry_after_seconds else http.HTTP_409_CONFLICT
        response = Response(
            {
                "detail": refusal.reason,
                "retry_after_seconds": refusal.retry_after_seconds,
            },
            status=code,
        )
        if refusal.retry_after_seconds:
            response["Retry-After"] = str(refusal.retry_after_seconds)
        return response

    return Response(
        SyncRunSerializer(
            {
                "status": run.status,
                "status_label": run.get_status_display(),
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "duration_seconds": run.duration_seconds,
                "request_count": run.request_count,
                "error": run.error,
            }
        ).data
    )
