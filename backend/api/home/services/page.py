"""Сборка главной — и единственное место, где решается, что человек увидит.

**Отбор по доступам делается здесь, на сервере.** Не в компоненте и не
фильтром на фронте: скрытая плитка, чьи числа всё равно приехали в ответе,
защищает ровно ни от чего — сумма долга утекла бы через инструменты
разработчика к тому, у кого нет «Сроков оплаты». Правило записано
в `PRD.md` §5.1, и это его исполнение.

**Плитка требует ту же страницу, куда ведёт.** Иначе она обещала бы переход,
который закончится отказом middleware, — а отказ в ответ на собственную
ссылку читается как поломка системы, а не как отсутствие прав.

**Считается только то, что будет показано.** Разворот техкарт и обход
каталога стоят заметно, и делать их ради плитки, которую этот человек
не увидит, — платить за чужой ответ.

**Пустой блок «Требует решения» — не пустое состояние, а хорошая новость**
(`DESIGN.md` §9). Но только когда данные вообще есть: до первого синка
счётчики равны нулю по другой причине, и различить их обязан сервер —
на фронте для этого нет ни одного признака.
"""

from dataclasses import dataclass
from datetime import date

from api.access import pages_for_user
from api.home.services import channels, earnings, misplaced, period, pulse, signals
from core.services.freshness import documents_synced_at, oldest_of, stock_synced_at

# Какая страница нужна каждой карточке. Ключи — из реестра `api/access.py`,
# и разойтись им не дадут тесты: несуществующий ключ здесь означал бы
# карточку, которую не увидит никто и никогда.
TILE_PAGES = {
    "misplaced": ("production", "supplies-materials"),
    "pulse": ("shipments-products",),
    "margins": ("profitability",),
    "changes": ("profitability",),
    "channels": ("channels",),
}


@dataclass(frozen=True)
class Access:
    """Что этому человеку разрешено видеть."""

    keys: frozenset[str]

    def allows(self, tile: str) -> bool:
        return bool(self.keys & set(TILE_PAGES[tile]))


def access_of(user) -> Access:
    return Access(keys=frozenset(page.key for page in pages_for_user(user)))


def build(user, *, today: date | None = None) -> dict:
    """Всё, что нужно главной, — уже урезанное по правам."""
    window = period.window(today)
    access = access_of(user)
    known = signals.known()

    payload: dict = {
        "period": {
            # Три формы месяца — по одной на каждое место, где он стоит:
            # «Итоги августа», «Август к июлю», «Сентябрь идёт».
            "label": window.current.label,
            "label_of": window.current.label_of,
            "first": window.current.first,
            "last": window.current.last,
            "earlier_label": window.earlier.label,
            "earlier_label_to": window.earlier.label_to,
            "running_label": window.running.label if window.running else None,
            "running_days": window.running_days if window.running else 0,
            "running_of_days": window.running.days if window.running else 0,
        },
        # Третье состояние блока сигналов. Без него пустой экран до первого
        # синка читается как «всё прекрасно», хотя мы просто не знаем ничего.
        "known": known,
        "signals": [],
        "sync_trouble": None,
        "misplaced": None,
        "pulse": None,
        "margins": None,
        "changes": None,
        "channels": None,
        "synced_at": oldest_of(stock_synced_at(), documents_synced_at()),
    }

    trouble = signals.sync_trouble()
    if trouble is not None:
        payload["sync_trouble"] = {
            "kind": trouble.kind,
            "label": trouble.label,
            "usual": trouble.usual,
            "affects": trouble.affects,
            "hours": trouble.hours,
        }

    if not known:
        return payload

    # Сигналы урезаются поштучно: у каждого своя страница, и человек
    # с одним «Расчётом производства» обязан увидеть свои три проверки,
    # а не пустой блок.
    payload["signals"] = [
        {
            "key": signal.key,
            # Обе подписи: какую показать, решает фронт по счётчику.
            # «резерв больше остатка» с зелёной галочкой читалось как
            # утверждение, что резерв больше остатка — и это хорошо.
            "label": signal.label,
            "label_clean": signal.label_clean,
            "note": signal.note,
            "note_clean": signal.note_clean,
            "count": signal.count,
            "items": [{"name": item.name, "note": item.note} for item in signal.items],
            "route": signal.route,
            "tone": signal.tone,
        }
        for signal in signals.of(today=today)
        if signal.page_key in access.keys
    ]

    if access.allows("misplaced"):
        payload["misplaced"] = _misplaced(today)
    if access.allows("pulse"):
        payload["pulse"] = _pulse(window)
    if access.allows("margins"):
        payload["margins"] = _margins(window)
    if access.allows("changes"):
        payload["changes"] = _changes(window)
    if access.allows("channels"):
        payload["channels"] = _channels(window)

    return payload


def _misplaced(today: date | None) -> dict:
    result = misplaced.of(today=today)
    return {
        "lost_kopecks": result.lost_kopecks,
        "lost_positions": result.lost_positions,
        "frozen_kopecks": result.frozen_kopecks,
        "frozen_positions": result.frozen_positions,
        "stock_kopecks": result.stock_kopecks,
        "demand_days": result.demand_days,
        "material_days": result.material_days,
        "to_brew": [
            {"name": row.name, "value": row.value, "note": row.note} for row in result.to_brew
        ],
        "lying_still": [
            {"name": row.name, "value": row.value, "note": row.note}
            for row in result.lying_still
        ],
        "lost_all": [
            {"name": row.name, "value": row.value, "note": row.note}
            for row in result.lost_all
        ],
        "frozen_all": [
            {"name": row.name, "value": row.value, "note": row.note}
            for row in result.frozen_all
        ],
    }


def _figure(figure) -> dict:
    return {
        "key": figure.key,
        "label": figure.label,
        "value": figure.value,
        "earlier": figure.earlier,
        "change": figure.change,
        "unit": figure.unit,
    }


def _pulse(window) -> dict:
    result = pulse.of(window)
    return {
        "shipped": [_figure(figure) for figure in result.shipped],
        "sold": [_figure(figure) for figure in result.sold],
        "consignment_kopecks": result.consignment_kopecks,
        "months": result.months,
    }


def _margins(window) -> list[dict]:
    return [
        {
            "name": row.name,
            "revenue_kopecks": row.revenue_kopecks,
            "margin": row.margin,
            "quantity": row.quantity,
        }
        for row in earnings.margins(window)
    ]


def _changes(window) -> list[dict]:
    return [
        {
            "name": row.name,
            "delta_kopecks": row.delta_kopecks,
            "now_kopecks": row.now_kopecks,
            "earlier_kopecks": row.earlier_kopecks,
        }
        for row in earnings.changes(window)
    ]


def _channels(window) -> list[dict]:
    return [
        {
            "name": row.name,
            "revenue_kopecks": row.revenue_kopecks,
            "documents": row.documents,
        }
        for row in channels.of(window)
    ]
