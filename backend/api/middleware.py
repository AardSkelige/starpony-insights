"""Серверная проверка доступа. Ходит перед каждым view, включая забытые.

Права на фронтенде — это удобство: скрыть пункт меню. Единственная настоящая
защита здесь, и она работает от списка в `api/access.py`, а не от того, что
разработчик не забыл навесить декоратор.
"""

from django.http import JsonResponse

from api.access import (
    PUBLIC_PREFIXES,
    SHARED_PREFIXES,
    matches,
    page_keys_for_path,
    user_has_any_page,
)


class PageAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self._deny(request) or self.get_response(request)

    def _deny(self, request) -> JsonResponse | None:
        path = request.path

        if matches(path, PUBLIC_PREFIXES):
            return None

        if not request.user.is_authenticated:
            return JsonResponse({"detail": "Требуется вход"}, status=401)

        if request.user.is_superuser:
            return None

        if matches(path, SHARED_PREFIXES):
            return None

        keys = page_keys_for_path(path)
        if not keys:
            # Путь не объявлен ни страницей, ни общим списком. Молча пропустить
            # его — значит открыть всем вошедшим то, о чём никто не подумал.
            return JsonResponse({"detail": "Путь не объявлен в реестре страниц"}, status=403)

        if not user_has_any_page(request.user, keys):
            return JsonResponse({"detail": "Нет доступа к разделу"}, status=403)

        return None
