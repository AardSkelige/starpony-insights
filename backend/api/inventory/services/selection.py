"""Выборка страницы «Инвентаризация».

Периода здесь нет намеренно — как у «Сроков оплаты». «Что давно не считали»
это состояние на сегодня, и период не сузил бы выборку, а спрятал бы часть
белых пятен: позиция, которую не считали ни разу, не попадает ни в какой
период вовсе и исчезла бы из ответа именно там, где она и есть ответ.

Сужают склад и папка номенклатуры: пересчитывают всегда один склад, и
«считали 06.08» без склада читается как «посчитали весь товар».
"""

from dataclasses import dataclass

from api.common.selection import Filters as BaseFilters
from core.models import Inventory
from core.services.catalogue import stocked


@dataclass(frozen=True)
class Filters(BaseFilters):
    """Поиск, склад, папка, порядок. Период унаследован, но не используется."""

    store: str = ""
    folder: str = ""
    ordering: str = "-money"


def stores() -> list[dict]:
    """Склады для фильтра — те, на которых пересчитывали хоть раз.

    Из инвентаризаций, а не из справочника складов: складов в учёте может
    быть больше, а фильтр, показывающий склад без единого пересчёта,
    отвечает пустой таблицей на верный вопрос.
    """
    names = (
        Inventory.objects.alive()
        .exclude(store_name="")
        .values_list("store_name", flat=True)
        .distinct()
        .order_by("store_name")
    )
    return [{"id": index, "name": name} for index, name in enumerate(names, start=1)]


def folders() -> list[str]:
    """Папки номенклатуры — по всей выборке, включая непересчитанные.

    Именно включая: папка, которую не открывали ни разу, обязана быть
    в списке — иначе выбрать «Производство/Тара» и увидеть её 27 позиций
    без единого пересчёта было бы нельзя.
    """
    return sorted(
        {folder for folder in stocked().values_list("folder", flat=True) if folder}
    )
