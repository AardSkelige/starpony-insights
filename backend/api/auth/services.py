"""Логика входа. Views остаются тонкими, запросы к БД живут здесь."""

from django.contrib.auth import authenticate, login, logout

from api.access import pages_for_user


def sign_in(request, username: str, password: str):
    """Проверить пару и открыть сессию. Возвращает пользователя или None."""
    user = authenticate(request, username=username, password=password)
    if user is None:
        return None
    login(request, user)
    return user


def sign_out(request) -> None:
    logout(request)


def profile(user) -> dict:
    """Всё, что фронтенду нужно знать о вошедшем: кто он и что ему видно.

    Меню строится из этого ответа, а не из своего списка на фронтенде: иначе
    появляется второй реестр страниц, который разъедется с `api/access.py`.
    """
    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.get_full_name() or user.username,
        # Подпись под именем. Собирается на сервере, а не на фронтенде:
        # правило «должность важнее прав» одно, и двух мест ему не нужно.
        "title": user.sidebar_title,
        "is_superuser": user.is_superuser,
        "pages": [
            {"key": p.key, "label": p.label, "group": p.group, "route": p.route}
            for p in pages_for_user(user)
        ],
    }
