"""Реестр страниц против реальных маршрутов Django.

Проверка идёт по `urlpatterns`, а не по самому реестру: только так находится
то, чего в реестре нет. Обход реестра нашёл бы лишь опечатки в нём самом.
"""

import re
from pathlib import Path

import pytest
from django.urls import URLPattern, URLResolver, get_resolver

from api.access import PAGES, PUBLIC_PREFIXES, SHARED_PREFIXES, matches, page_keys_for_path


def collect_routes(resolver=None, prefix: str = "/") -> list[str]:
    """Все маршруты проекта, с подставленным началом пути."""
    resolver = resolver or get_resolver()
    routes: list[str] = []
    for entry in resolver.url_patterns:
        pattern = prefix + str(entry.pattern)
        if isinstance(entry, URLResolver):
            routes.extend(collect_routes(entry, pattern))
        elif isinstance(entry, URLPattern):
            routes.append(pattern)
    return routes


@pytest.mark.parametrize("route", collect_routes())
def test_every_route_is_declared(route):
    """Каждый маршрут принадлежит странице, общему списку или публичному.

    Непокрытый маршрут не «работает как раньше» — он закрыт для всех, кроме
    суперпользователя. Тест ловит это до выкатки, а не пользователь после.
    """
    covered = (
        matches(route, PUBLIC_PREFIXES)
        or matches(route, SHARED_PREFIXES)
        or bool(page_keys_for_path(route))
    )
    assert covered, (
        f"Маршрут {route} не объявлен в api/access.py. Добавьте страницу "
        f"с этим префиксом либо внесите путь в PUBLIC_PREFIXES / SHARED_PREFIXES."
    )


def test_page_keys_are_unique():
    keys = [page.key for page in PAGES]
    assert len(keys) == len(set(keys))


def test_page_routes_are_unique():
    routes = [page.route for page in PAGES]
    assert len(routes) == len(set(routes))


def test_api_prefixes_are_well_formed():
    for page in PAGES:
        assert page.api_prefixes, f"У страницы {page.key} нет ни одного префикса API"
        for prefix in page.api_prefixes:
            assert prefix.startswith("/api/"), f"{prefix}: префикс должен начинаться с /api/"
            # Без завершающего слэша префикс "/api/supplies" поймал бы и
            # "/api/suppliers/" — соседний раздел с другими правами.
            assert prefix.endswith("/"), f"{prefix}: префикс должен заканчиваться слэшем"


def test_shared_and_public_do_not_overlap_pages():
    """Общий путь не должен пересекаться с путём страницы.

    Иначе доступ, выданный страницей, ничего не значит: путь и так открыт всем.
    """
    for page in PAGES:
        for prefix in page.api_prefixes:
            assert not matches(prefix, PUBLIC_PREFIXES), f"{prefix} открыт публично"
            assert not matches(prefix, SHARED_PREFIXES), f"{prefix} открыт всем вошедшим"


def test_every_page_has_an_icon():
    """У каждой страницы реестра есть иконка на фронтенде.

    В свёрнутом сайдбаре виден только значок, поэтому пункт без
    иконки превращается в пустое место. Проверка идёт со стороны бэкенда
    намеренно: реестр — здесь, и забывают обычно после добавления строки в него,
    а не при правке фронтенда.
    """
    icons = Path(__file__).resolve().parents[2] / "frontend/src/app/layout/nav-icons.ts"
    if not icons.exists():
        pytest.skip("Фронтенд не собран рядом — проверять нечего")

    source = icons.read_text(encoding="utf-8")
    body = source[source.index("NAV_ICONS: Record<string, LucideIcon> = {") :]
    declared = set(re.findall(r'^\s+"?([\w-]+)"?:\s*\w+,', body, re.M))

    missing = {page.key for page in PAGES} - declared
    assert not missing, (
        f"Нет иконок для страниц: {', '.join(sorted(missing))}. "
        f"Добавьте их в frontend/src/app/layout/nav-icons.ts"
    )
