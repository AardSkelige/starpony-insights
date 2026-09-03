"""Второе и третье звенья цепочки: партия → сырьё → что закупить.

Разворачивание берётся готовым (`core.services.materials.explode`): сырьё
считается по техкартам рекурсивно, потому что производство идёт в два шага —
сырьё в замес, замес в розлив, — и прямой состав показал бы полуфабрикат,
которого не закупают.

**Своего расчёта здесь почти нет.** Новое одно: сопоставить нужное с тем,
что лежит, и сказать, чего не хватает. Всё остальное уже посчитано соседями
и переиспользуется дословно — иначе два места считали бы одно число.

**Нехватка меряется от свободного остатка, а не от неснижаемого.**
Неснижаемый остаток проставлен у десяти позиций сырья из двухсот тринадцати,
и одна из них пробита давно, до всякой партии: отдушки «Лесные ягоды» лежит
2,4 г при минимуме 70. Вычти мы минимум из доступного, эти 67,6 г вошли бы
в дефицит партии, к которой отношения не имеют. Правило, работающее
у пяти процентов строк, не должно менять смысл главного числа.

Поэтому минимум идёт **вторым сигналом**, отдельно от нехватки, и говорит
о двух разных вещах: остаток уже ниже минимума — и остаток **станет** ниже
после этой партии. Второе встречается там, где первого нет, и на боевых
данных таких три из ста: экстракта зелёного чая 1048 г при минимуме 500,
партия съедает 560, остаётся 488. Написать про него «хватает» и замолчать —
молчаливая полуправда.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from core.models import Document, DocumentKind, Product, ProductKind, Stock
from core.services import lead_time
from core.services.documents import alive
from core.services.materials import MaterialPath, explode, plans_by_product
from core.services.purchase_prices import (
    PurchasePrice,
    cost_of,
    last_purchase_prices,
)

logger = logging.getLogger(__name__)


class LineProblem:
    """Почему строка партии не пошла в расчёт.

    Строка не выбрасывается молча ни в одном из случаев: сломанная ссылка
    и опечатка в артикуле выглядят одинаково, и «посчитали по трём товарам
    из четырёх» ничем не отличается на вид от «посчитали по всем».
    """

    UNKNOWN = "unknown"        # артикула нет в учёте
    ARCHIVED = "archived"      # товар есть, но убран в архив — таких 16
    NO_PLAN = "no_plan"        # техкарты нет, разворачивать не во что — такой 1
    # Отмечен, а количество предложить не из чего: товар не продавался
    # за период либо остаток неизвестен. Раньше такая позиция выпадала
    # из расчёта молча — галочка стояла, а в партии её не было.
    NO_QUANTITY = "no_quantity"


@dataclass(frozen=True)
class BatchLine:
    """Строка партии: что произвести и сколько."""

    article: str
    # `None` — количество предложить не из чего, и человек его не вводил.
    # Ноль сюда не годится: он читался бы как «произвести ноль».
    quantity: int | None
    # `None` — товар не найден либо не годится; тогда заполнен `problem`.
    product: Product | None
    problem: str | None

    @property
    def counts(self) -> bool:
        return (
            self.product is not None
            and self.problem is None
            and self.quantity is not None
        )


@dataclass
class Need:
    """Сколько одного материала нужно на партию и чем это обеспечено."""

    product: Product

    quantity: Decimal
    # Свободный остаток. `None` — строки остатка в отчёте нет вовсе.
    available: Decimal | None
    # Сколько докупить. `None` — остаток неизвестен, и вычитать не из чего;
    # ноль означал бы «всё есть», а это другое утверждение об учёте.
    shortage: Decimal | None
    # Что останется после партии. Отрицательным не бывает: если не хватает,
    # останется ноль, а недостающее уедет в `shortage`.
    after: Decimal | None

    min_balance: Decimal | None
    below_min_now: bool
    below_min_after: bool

    # Материал убран в архив, а действующая техкарта его всё ещё требует.
    # Значит карту забыли поправить вместе с линейкой — и без пометки
    # страница молча предлагала бы закупать снятое с производства.
    # На боевых данных так и было: этикетки «(Старое)» и триггер висели
    # в трёх кондиционерах как «остатка в отчёте нет», и причина —
    # архив, а не пробел в учёте (03.09).
    archived: bool

    price: PurchasePrice | None
    # Во сколько обойдётся докупка недостающего. `None` — неизвестна цена
    # или неизвестен остаток.
    cost_kopecks: int | None
    waiting: lead_time.LeadTime

    # Из каких изделий пришёл материал и какими путями — объяснение числа
    # (`CLAUDE.md` §4). Сумма по путям равна `quantity`.
    via: list[MaterialPath] = field(default_factory=list)
    sources: dict[int, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class Batch:
    """Партия целиком: что производим, что для этого нужно, чего не хватает."""

    lines: list[BatchLine]
    needs: list[Need]

    @property
    def shortages(self) -> list[Need]:
        return [need for need in self.needs if need.shortage and need.shortage > 0]

    @property
    def purchase_kopecks(self) -> int:
        """Во сколько обойдётся докупка. Считается по тем, у кого есть цена.

        Рядом обязано ехать `priced_shortages_count`, иначе сумма выглядит
        итогом по всем недостающим позициям, а она итог по части.
        """
        return sum(need.cost_kopecks or 0 for need in self.shortages)

    @property
    def priced_shortages_count(self) -> int:
        return sum(1 for need in self.shortages if need.cost_kopecks is not None)


@dataclass
class _Collected:
    """Накопитель по одному материалу, пока идёт разворачивание партии."""

    product: Product
    quantity: Decimal = Decimal(0)
    via: list[MaterialPath] = field(default_factory=list)
    # Изделие → сколько материала пришло от него. И объяснение числа,
    # и ответ на «из-за чего его столько».
    sources: dict[int, Decimal] = field(default_factory=dict)


def of(batch: dict[str, int | None]) -> Batch:
    """Развернуть партию до сырья и сверить с остатками."""
    plans = plans_by_product()
    lines = _lines(batch, plans)

    collected: dict[int, _Collected] = {}
    for line in lines:
        if not line.counts:
            continue
        assert line.product is not None and line.quantity is not None
        for need in explode(line.product, Decimal(line.quantity), plans=plans):
            entry = collected.setdefault(need.product.pk, _Collected(need.product))
            entry.quantity += need.quantity
            entry.sources[line.product.pk] = (
                entry.sources.get(line.product.pk, Decimal(0)) + need.quantity
            )
            for path in need.via:
                _merge_path(entry.via, path)

    return Batch(lines=lines, needs=_needs(list(collected.values())))


def _lines(batch: dict[str, int | None], plans: dict) -> list[BatchLine]:
    """Сопоставить артикулы из адресной строки с номенклатурой.

    Порядок ответа — тот, в котором артикулы пришли: человек собирал партию
    в своём порядке, и пересортировать её значит заставить его искать
    свою строку заново.
    """
    found: dict[str, Product] = {}
    # Порядок задан явно: у `Product.article` нет ограничения уникальности
    # ни в модели, ни в синхронизации, и при двух товарах с одним артикулом
    # выбор иначе зависел бы от порядка строк в базе и менялся между
    # запросами без всякого признака. На боевых данных дублей нет — это
    # мина, а не поломка, но тихая. Так же устроен `plans_by_product`.
    for product in (
        Product.objects.alive()
        .filter(kind=ProductKind.PRODUCT, article__in=list(batch))
        .select_related("uom")
        .order_by("article", "-ms_updated")
    ):
        if product.article in found:
            logger.warning(
                "Артикул «%s» у нескольких товаров. Считаем по «%s», "
                "игнорируем «%s».",
                product.article, found[product.article].name, product.name,
            )
            continue
        found[product.article] = product

    lines = []
    for article, quantity in batch.items():
        product = found.get(article)
        if product is None:
            problem = LineProblem.UNKNOWN
        elif product.archived:
            problem = LineProblem.ARCHIVED
        elif product.pk not in plans:
            problem = LineProblem.NO_PLAN
        elif quantity is None:
            # Отмечен, но предложить нечего. Возвращается названным,
            # а не выбрасывается: галочка стоит, и человек вправе знать,
            # почему позиции нет в расчёте.
            problem = LineProblem.NO_QUANTITY
        else:
            problem = None

        # Товар кладётся в строку и тогда, когда с ним что-то не так: у него
        # есть название, и «Кондиционер Peachy Banana — в архиве» человек
        # поймёт, а «200.008.05 — в архиве» заставит идти в учёт за именем.
        lines.append(
            BatchLine(
                article=article, quantity=quantity, product=product, problem=problem
            )
        )
    return lines


def _merge_path(via: list[MaterialPath], path: MaterialPath) -> None:
    """Сложить одинаковые пути, а не завести второй такой же.

    Тот же довод, что у `materials._add_path`: два товара партии приходят
    к материалу одной и той же цепочкой техкарт, и держать её дважды значит
    показать человеку два одинаковых объяснения вместо одного числа.
    """
    for index, existing in enumerate(via):
        if existing.chain == path.chain:
            via[index] = MaterialPath(path.chain, existing.quantity + path.quantity)
            return
    via.append(path)


def _needs(collected: list[_Collected]) -> list[Need]:
    """Собрать сырьё вместе с остатком, минимумом, ценой и сроком поставки."""
    material_ids = [entry.product.pk for entry in collected]
    stocks = {
        row.product_id: row for row in Stock.objects.filter(product_id__in=material_ids)
    }
    prices = last_purchase_prices(material_ids)
    waiting = _lead_times({price.supplier_id for price in prices.values()})

    needs = [
        _need_of(
            entry,
            stocks.get(entry.product.pk),
            prices.get(entry.product.pk),
            waiting,
        )
        for entry in collected
    ]

    # Сверху — то, чего не хватает, и внутри по величине нехватки. Дальше
    # неизвестное, потом благополучное: список читают сверху и до первой
    # строки, которая не требует действия.
    needs.sort(
        key=lambda need: (
            0 if need.shortage else (1 if need.shortage is None else 2),
            -(need.shortage or Decimal(0)),
            need.product.name,
        )
    )
    return needs


def _need_of(
    entry: _Collected,
    stock: Stock | None,
    price: PurchasePrice | None,
    waiting: dict[int, lead_time.LeadTime],
) -> Need:
    product, quantity = entry.product, entry.quantity
    available = stock.available if stock else None

    shortage = after = None
    if available is not None:
        shortage = max(Decimal(0), quantity - available)
        after = max(Decimal(0), available - quantity)

    minimum = product.min_balance
    return Need(
        product=product,
        quantity=quantity,
        available=available,
        shortage=shortage,
        after=after,
        min_balance=minimum,
        archived=product.archived,
        # Уже ниже минимума — состояние склада, к этой партии отношения
        # не имеющее. На боевых данных таких четыре из десяти.
        below_min_now=bool(
            minimum and available is not None and available < minimum
        ),
        # Станет ниже минимума из-за партии — сигнал ровно для одного случая:
        # материала хватает, партия пройдёт, но следом закупаться придётся
        # срочно. Экстракта зелёного чая 1048 г при минимуме 500, партия
        # съест 560, останется 488.
        #
        # Два условия отсекают шум, и оба нашлись на боевых данных.
        # Уже пробитый минимум — состояние склада, к партии отношения
        # не имеющее, и засчитывать давнюю дыру этой партии нельзя.
        # А там, где не хватает вовсе, `after` равен нулю не потому, что
        # партия съела запас, а потому, что её не выпустить: строка и так
        # говорит «докупить 7060 г», и второй значок рядом — не второй
        # довод, а повтор первого.
        below_min_after=bool(
            minimum
            and after is not None
            and after < minimum
            and not (available is not None and available < minimum)
            and not (shortage and shortage > 0)
        ),
        price=price,
        cost_kopecks=(
            cost_of(shortage, price) if price and shortage and shortage > 0 else None
        ),
        waiting=(
            waiting.get(price.supplier_id, lead_time.NOTHING)
            if price
            else lead_time.NOTHING
        ),
        via=sorted(entry.via, key=lambda path: -path.quantity),
        sources=entry.sources,
    )


def _lead_times(supplier_ids: set[int]) -> dict[int, lead_time.LeadTime]:
    """Срок поставки по каждому поставщику — один запрос на всех.

    Медиана по **его** приёмкам, а не по всем: у «Химпитерторга» 7,5 дня,
    у «Принтеца» ровно 0 — у него забирают. Общая медиана не описывает
    ни того, ни другого, и «везут 1 день» отправило бы человека ждать
    неделю (`core/services/lead_time.py`).
    """
    if not supplier_ids:
        return {}

    grouped: dict[int, list[Document]] = defaultdict(list)
    for supply in (
        alive(DocumentKind.SUPPLY)
        .filter(agent_id__in=supplier_ids)
        .select_related("purchase_order")
    ):
        grouped[supply.agent_id].append(supply)

    return {agent_id: lead_time.of(items) for agent_id, items in grouped.items()}
