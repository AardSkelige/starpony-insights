"""Регулярность поставок: как часто поставщик привозит.

Живёт у раздела, а не в `core/`: больше это никому не нужно. Переедет,
когда понадобится второму, — не раньше.

**Считается медианой, а не средним** — по той же причине, что срок поставки
(`core/services/lead_time.py`). У «Полицвета» на боевых данных среднее 22,5
дня против медианы 6,5: один разрыв в 73 дня утащил среднее вчетверо.
У «ИП Белых» — 11,9 против 4. Спрашивают «как часто обычно», и отвечает
на это медиана.

**Интервал считается между днями, а не между документами.** Приёмки от одного
поставщика шесть раз падают в один день — у «Интернет Решений» 31 марта их
три штуки. Считай мы по документам, получились бы интервалы в ноль дней:
это не цикл поставки, а одна поставка, разбитая на бумаги. Дедупликация
меняет числа заметно — у тех же «Интернет Решений» среднее 13,7 → 17,8,
медиана 8 → 11.

**День берётся по местному календарю, а не по UTC.** Иначе приёмка, принятая
в час ночи, уезжает в предыдущие сутки, и три документа одним днём считаются
двумя днями поставок — ровно то, ради чего дедупликация и вводилась.
"""

import statistics
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from core.dates import local_date
from core.models import Document


@dataclass(frozen=True)
class Regularity:
    """Как часто возит поставщик и из чего это получено."""

    # Медиана интервала в днях. `None` — поставка была одна, и промежутка
    # между ними не существует. Ноль читался бы как «возит каждый день».
    days: Decimal | None
    # Сколько промежутков удалось измерить: на N дней поставок их N−1.
    gaps: int
    # Дней поставок — не приёмок: три документа одним днём это одна поставка.
    delivery_days: int

    min_days: int | None
    max_days: int | None
    # Среднее — только в объяснении, рядом с медианой. Расхождение между ними
    # само говорит, насколько поставки рваные.
    average_days: Decimal | None


NOTHING = Regularity(
    days=None,
    gaps=0,
    delivery_days=0,
    min_days=None,
    max_days=None,
    average_days=None,
)


def of(supplies: Iterable[Document]) -> Regularity:
    """Регулярность по набору приёмок одного поставщика."""
    days = sorted({local_date(supply.moment) for supply in supplies})
    return _from_days(days)


def _from_days(days: list[date]) -> Regularity:
    if len(days) < 2:
        return Regularity(
            days=None,
            gaps=0,
            delivery_days=len(days),
            min_days=None,
            max_days=None,
            average_days=None,
        )

    gaps = [(later - earlier).days for earlier, later in zip(days, days[1:])]
    return Regularity(
        days=Decimal(str(statistics.median(gaps))),
        gaps=len(gaps),
        delivery_days=len(days),
        min_days=min(gaps),
        max_days=max(gaps),
        average_days=Decimal(str(round(statistics.mean(gaps), 1))),
    )
