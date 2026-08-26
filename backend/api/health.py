"""Проверка живости для мониторинга.

Отвечать 200, не потрогав базу, — худший вид health-check: приложение
рапортует «жив», пока пул соединений мёртв и все страницы отдают 500.
Поэтому запрос к Postgres здесь обязателен.
"""

from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        # Наружу — только факт. Текст ошибки Postgres содержит имя базы,
        # пользователя и адрес, а эндпоинт открыт без аутентификации.
        return Response({"status": "error", "database": "unavailable"}, status=503)

    return Response({"status": "ok", "database": "ok"})
