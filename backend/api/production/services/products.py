"""Первое звено цепочки: что кончается и сколько этого произвести.

Отвечает на вопрос, которого нет в учёте. Остатки МойСклад показывает сам,
и открыть их — не работа; чего он не говорит, так это **много это или мало**.
Двенадцать репеллентов выглядят запасом, пока не выяснится, что их берут
по четыре в день. Отсюда единственная величина, ради которой страница
существует: на сколько дней хватит того, что лежит.

**Товар — это то, у чего есть артикул** (решение 02.09). Материалы артикула
не имеют, и здесь их быть не должно: это список того, что производят,
а не того, из чего производят.

**Запас считается тем же `coverage.of`, что у материалов.** Вопрос другой —
там «пора ли закупать», здесь «пора ли варить», — а число одно, и второй
копии у него быть не должно: разойдись они, две страницы за один период
показали бы разный запас одного и того же товара.
"""

import math
from dataclasses import dataclass
from decimal import Decimal


from django.db.models import QuerySet

from api.common.selection import matching, within
from api.production.services.selection import Filters
from core.models import DocumentKind, DocumentPosition, Product, Stock
from core.services import catalogue, coverage
from core.services.documents import alive, positions_in
from core.services.materials import plans_by_product


@dataclass(frozen=True)
class ProductRow:
    """Товар вместе с ответом «надолго ли хватит» и «сколько варить»."""

    product: Product
    # Свободный остаток. `None` — строки остатка нет в отчёте вовсе;
    # ноль здесь означал бы «кончился», а это другое утверждение об учёте.
    available: Decimal | None
    left: coverage.Coverage
    # Сколько произвести, чтобы хватило на горизонт. `None` там, где считать
    # не из чего: товар не продавался за период (восполнять нечего) либо
    # остаток неизвестен (неясно, от чего отталкиваться). Ноль сюда
    # не годится — он значит «производить не надо», а мы просто не знаем.
    suggested: int | None
    # Без техкарты развернуть товар до сырья нечем. Один такой на 57 —
    # «Таблетка-мыло для лап». Не ошибка расчёта, а пробел в учёте,
    # и страница обязана назвать его словами, а не молча пропустить строку.
    has_plan: bool
    # Сколько обещано под заказы покупателей. Показывается только когда
    # больше нуля: строка «в резерве 0» есть у всех и не сообщает ничего.
    #
    # Заведено 04.09. Свободный остаток на странице был всегда, а откуда
    # он получен — нет: «остаток 5» при шести на складе выглядел ошибкой
    # данных. И это же ответ на сигнал главной «заказов нечем закрыть»:
    # резерв больше остатка виден здесь, а не только в разборе строки.
    reserved: Decimal


def shipment_positions(filters: Filters) -> QuerySet[DocumentPosition]:
    """Позиции отгрузок за период — расход, от которого считается запас.

    **Отгрузки, а не оплаченные продажи.** Товар, ушедший по договору комиссии,
    ещё не продан, но со склада его уже нет, и восполнять его надо наравне
    с остальным. Тот же довод у подарков: отданное даром произведено так же,
    как проданное, и вычесть его значило бы недосчитаться варки.
    """
    return within(
        positions_in(alive(DocumentKind.DEMAND)), filters.date_from, filters.date_to
    )


def rows(
    filters: Filters, *, articles: list[str] | None = None
) -> list[ProductRow]:
    """Все товары с артикулом, сверху — те, что кончаются раньше.

    `articles` сужает выборку до перечисленных — этим пользуется разрешение
    количеств партии (`payload.resolve`): ему нужны предложения по десятку
    отмеченных позиций, а не по всем пятидесяти семи. Без сужения полное
    верхнее звено — каталог, продажи за период и техкарты — считалось бы
    на каждое нажатие «плюс».
    """
    # Не `catalogue`: так называется модуль `core/services/catalogue.py`,
    # который этот файл импортирует, — локальное имя перекрыло бы его внутри
    # функции, и обращение к `catalogue.goods()` упало бы с `AttributeError`.
    # Та же причина, что у `chosen` в «Товарах в отгрузках».
    chosen = _catalogue(filters.search, articles=articles)
    positions = shipment_positions(filters)
    span = coverage.span_of(positions, filters.date_from, filters.date_to)

    left_by_product = coverage.by_product(chosen, positions, span)
    plans = plans_by_product()
    reserved = {
        stock.product_id: stock.reserved
        for stock in Stock.objects.filter(product__in=chosen, reserved__gt=0)
    }

    result = [
        _row_of(
            product,
            left_by_product[product.pk],
            filters.horizon,
            product.pk in plans,
            reserved.get(product.pk, Decimal(0)),
        )
        for product in chosen
    ]

    # Сначала то, что кончается раньше — это и есть срочность производства.
    #
    # **При равном запасе выше идёт то, что уходит быстрее.** Восемнадцать
    # позиций разом показывают «хватит на 0 дней», и алфавит внутри нуля
    # ставил «Bubblegum» (0,129 шт/день) выше «Зелёного чая» (0,535 шт/день),
    # хотя второго не хватает вчетверо сильнее. Ноль дней у обоих —
    # но дыра разная, и первым варят большую.
    #
    # Неизвестный запас — в конец: он не «очень большой», про него просто
    # нечего сказать, и держать такие строки среди спокойных значило бы
    # выдать незнание за благополучие.
    result.sort(
        key=lambda row: (
            row.left.days_left is None,
            row.left.days_left if row.left.days_left is not None else 0,
            -row.left.per_day,
            row.product.name,
        )
    )
    return result


def _catalogue(search: str, *, articles: list[str] | None = None) -> list[Product]:
    """Товары, которые производят. Определение — общее, в `core/services/catalogue.py`.

    Своим здесь остаётся только отбор страницы: поиск и сужение до партии.
    Что именно считать товаром — знание домена, и оно одно на проект.
    """
    queryset = catalogue.goods().select_related("uom")

    if articles is not None:
        queryset = queryset.filter(article__in=articles)

    if search:
        # Условие общее с остальными разделами, только путь до товара пустой:
        # здесь строка таблицы и есть товар, а не позиция документа.
        queryset = queryset.filter(matching(search, prefix=""))

    return list(queryset)


def _row_of(
    product: Product,
    left: coverage.Coverage,
    horizon: int,
    has_plan: bool,
    reserved: Decimal,
) -> ProductRow:
    return ProductRow(
        product=product,
        available=left.available,
        left=left,
        suggested=suggested_for(left.per_day, left.available, horizon),
        has_plan=has_plan,
        reserved=reserved,
    )


def suggested_for(
    per_day: Decimal, available: Decimal | None, horizon: int
) -> int | None:
    """Сколько произвести, чтобы хватило на горизонт.

        произвести = темп продаж × горизонт − свободный остаток

    **Вверх, а не вниз.** Половину флакона не варят, и «94,3 штуки» —
    это 95: недоварить значит вернуться к той же строке через неделю.
    Обратное правило у `coverage.days_left`, и это не разнобой: там округление
    вниз, потому что обещать день, которого нет, дороже, чем недообещать.

    `None` там, где считать не из чего. Товар не продавался за период —
    восполнять нечего, и предложить партию значило бы предложить склад.
    Остаток неизвестен — неясно, что вычитать, и подставить ноль означало бы
    выдать незнание за пустой склад.
    """
    if available is None or per_day <= 0:
        return None
    return max(0, math.ceil(per_day * horizon - available))


def page(filters: Filters) -> dict:
    """Верхнее звено целиком — то, что уходит на экран."""
    result = rows(filters)
    return {
        "rows": [_cells(row, filters.horizon) for row in result],
        "summary": _summary(result),
        "horizon": filters.horizon,
    }


def _cells(row: ProductRow, horizon: int) -> dict:
    return {
        "product_id": row.product.pk,
        "article": row.product.article,
        "name": row.product.name,
        "folder": row.product.folder,
        "uom": row.product.uom.name if row.product.uom else "",
        "available": row.available,
        "coverage": {
            "quantity": row.left.quantity,
            "per_day": row.left.per_day,
            "days_of_period": row.left.days_of_period,
            "days_left": row.left.days_left,
            # Считается на сервере: пороги и текст предупреждения обязаны
            # меняться вместе.
            "level": coverage.level(row.left.days_left),
        },
        "suggested": row.suggested,
        # Горизонт едет в каждой строке, а не только в шапке: без него
        # «произвести 61» не собирается в формулу, а формула обязана
        # складываться из полученного (`CLAUDE.md` §4).
        "horizon": horizon,
        "has_plan": row.has_plan,
        "reserved": row.reserved,
    }


def _summary(result: list[ProductRow]) -> dict:
    """Итог по **показанному**, а не по всей базе.

    Знаменатель сужается поиском вместе со строками: иначе, найдя один товар,
    человек увидел бы «33 из 57 кончаются» — число про множество, которого
    на экране нет (`DESIGN.md` §8).
    """
    return {
        "products_count": len(result),
        "critical_count": sum(
            1
            for row in result
            if row.left.days_left is not None
            and row.left.days_left <= coverage.CRITICAL_DAYS
        ),
        # Рядом с предыдущим обязательно: «кончается 33 из 57» без него
        # читается как «остальные 24 в порядке», а про часть из них мы
        # просто ничего не знаем.
        "unknown_count": sum(1 for row in result if row.left.days_left is None),
        "without_plan_count": sum(1 for row in result if not row.has_plan),
    }
