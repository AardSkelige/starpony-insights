"""Постраничный контроль доступа. Единый источник правды.

Отсюда берут правду три потребителя: middleware (серверная защита), меню
на фронтенде и админка выдачи доступов. Второго списка страниц в проекте нет.

**Умолчание — запрет.** Путь, не объявленный ни страницей, ни общим списком,
недоступен никому, кроме суперпользователя. В Horse Bio умолчание обратное,
и там 16 маршрутов из 79 оказались открыты всем вошедшим — включая тот, что
запускает полную синхронизацию. Ошибка забывчивости должна закрывать доступ,
а не открывать.

Новая страница = новая строка здесь. Забыли — упадёт `test_access_registry`.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Page:
    key: str          # стабильный идентификатор, совпадает с ключом на фронтенде
    label: str        # подпись в меню и в админке доступов
    group: str        # группа сайдбара; пустая строка — пункт вне групп
    route: str        # путь на фронтенде
    api_prefixes: tuple[str, ...] = field(default=())


# Порядок и группы держим синхронными с сайдбаром (DESIGN.md §4): админка
# доступов показывает то же деление, которое человек видит в меню.
PAGES: tuple[Page, ...] = (
    Page("home", "Главная", "", "/", ("/api/home/",)),

    Page("shipments-products", "Товары в отгрузках", "Склад",
         "/shipments/products", ("/api/shipments/products/",)),
    Page("shipments-materials", "Материалы в отгрузках", "Склад",
         "/shipments/materials", ("/api/shipments/materials/",)),
    Page("supplies-materials", "Материалы в приёмках", "Склад",
         "/supplies/materials", ("/api/supplies/materials/",)),
    Page("suppliers", "Поставщики", "Склад",
         "/suppliers", ("/api/suppliers/",)),
    Page("production", "Расчёт производства", "Склад",
         "/production", ("/api/production/",)),
    Page("inventory", "Инвентаризация", "Склад",
         "/inventory", ("/api/inventory/",)),

    Page("deadlines", "Сроки оплаты", "Деньги",
         "/deadlines", ("/api/deadlines/",)),
    Page("profitability", "Прибыльность", "Деньги",
         "/profitability", ("/api/profitability/",)),

    Page("channels", "Каналы продаж", "Каналы",
         "/channels", ("/api/channels/",)),
)

# Доступно без входа. Список короткий и остаётся таким: каждая строка здесь —
# дыра в периметре, и она должна быть видна целиком с одного взгляда.
PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/auth/login/",
    "/api/auth/csrf/",
    "/healthz",
    "/admin/login/",
    "/static/",
)

# Доступно любому вошедшему, независимо от выданных страниц.
SHARED_PREFIXES: tuple[str, ...] = (
    "/api/auth/logout/",
    "/api/auth/me/",
    "/api/schema/",
    "/admin/",
)

PAGES_BY_KEY = {page.key: page for page in PAGES}

# Длинный префикс проверяем первым: "/api/shipments/products/" специфичнее,
# чем "/api/shipments/", и доступ к одной странице не должен открывать соседнюю.
_PREFIX_TO_KEYS: tuple[tuple[str, frozenset[str]], ...] = tuple(
    sorted(
        (
            (prefix, frozenset(p.key for p in PAGES if prefix in p.api_prefixes))
            for prefix in {prefix for page in PAGES for prefix in page.api_prefixes}
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)


def matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def page_keys_for_path(path: str) -> frozenset[str]:
    """Ключи страниц, которым принадлежит путь. Пустое множество — путь ничей."""
    for prefix, keys in _PREFIX_TO_KEYS:
        if path.startswith(prefix):
            return keys
    return frozenset()


def user_has_any_page(user, keys: frozenset[str]) -> bool:
    """Есть ли у пользователя хотя бы одна из перечисленных страниц."""
    return user.page_access.filter(page_key__in=keys).exists()


def pages_for_user(user) -> tuple[Page, ...]:
    """Страницы, доступные пользователю, — для меню и админки доступов."""
    if user.is_superuser:
        return PAGES
    granted = set(user.page_access.values_list("page_key", flat=True))
    return tuple(page for page in PAGES if page.key in granted)
