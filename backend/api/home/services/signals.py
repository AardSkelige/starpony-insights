"""«Требует решения»: шесть проверок, каждая со ссылкой в свой раздел.

**Состояние на сейчас, а не за месяц.** Периода у этих проверок нет вовсе:
товар либо кончился сегодня, либо нет. Единственное, где период появляется, —
внутри расчёта запаса: чтобы сказать «хватит на три дня», нужен темп продаж,
и он берётся за шестьдесят дней. Это окно названо на экране, потому что
меняет ответ.

**Состояний три, а не два.** Есть что разобрать / всё в порядке / данных
ещё нет. До первого синка счётчики равны нулю, и без третьего состояния
пустой экран читается как «всё прекрасно», хотя мы просто ничего не знаем
(`PRD.md` §5.1).

**Сигнал знает, какая страница ему нужна.** Не для красоты: сборка выкидывает
из ответа всё, к чему у человека нет доступа, — иначе сумма долга утекла бы
через главную к тому, кому её видеть нельзя. Правило то же, что у ссылки:
сигнал ведёт туда, где его разбирают, и требует ровно ту страницу.

**Порог берётся оттуда же, откуда его берёт страница разбора.** `CRITICAL_DAYS`
и `LOW_DAYS` живут в `core/services/coverage.py`: разойдись они, главная
сообщала бы о четырнадцати днях, а «Расчёт производства» красил строку
с тридцати.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import F, Sum
from django.utils import timezone

from api.common.selection import within
from core.dates import today as local_today
from core.models import DocumentKind, ProductKind, ProfitDay, Stock, SyncKind
from api.home.services import restock
from core.services import catalogue, consumption, coverage, freshness
from core.services.documents import alive, positions_in
from core.text import with_plural

# Окно спроса для расчёта запаса. Шире месяца намеренно: за месяц не отличить
# «кончилось» от «не продавалось» — товар, проданный трижды и кончившийся,
# и товар, не проданный ни разу, дают одинаковый ноль остатка.
DEMAND_DAYS = 60

# За сколько дней до конца бить тревогу по сырью. Месяц, а не две недели:
# у сырья к сроку расхода добавляется срок поставки, и медиана по StarPony —
# от одного дня у местных до трёх недель у остальных (`core/services/lead_time.py`).
MATERIAL_DAYS = 30

# Ниже этого убытка позиция в сигнал не попадает. Пятьсот рублей — не порог
# значимости, а порог **разговора**: за меньшее не звонят поставщику
# и не меняют прайс. На боевых из пяти убыточных позиций три стоят 64 ₽,
# 52 ₽ и 10 ₽ — они делали строку вечно красной, а решения из неё не следовало.
MIN_LOSS_KOPECKS = 50_000

# После скольких часов молчания синхронизация считается сломанной.
# Пороги разные, потому что расписания разные: остатки идут каждые 15 минут,
# документы — раз в сутки ночью. Один порог на оба означал бы либо ложную
# тревогу по документам, либо слепоту к остаткам на целые сутки.
STATE_STALE_HOURS = 2
DOCUMENTS_STALE_HOURS = 36


@dataclass(frozen=True)
class Found:
    """Одна найденная позиция: что именно и почему попало."""

    name: str
    note: str


@dataclass(frozen=True)
class Signal:
    """Одна проверка: сколько нашлось, что именно и куда с этим идти."""

    key: str
    # Подпись при находках: «товар кончился».
    label: str
    # Подпись, когда не нашлось ничего. Отдельная, а не та же самая:
    # «резерв больше остатка» с зелёной галочкой читается как «резерв больше
    # остатка — и это хорошо». Утверждение обязано менять форму вместе
    # с ответом, иначе галочка спорит с текстом.
    label_clean: str
    # Уточнение под подписью: без него «21» не отличить от «21 чего именно».
    note: str
    # Уточнение, когда не нашлось ничего. Отдельное по той же причине,
    # что и подпись: «обещано ровно то, что есть» с пояснением «резерв
    # в заказах превышает остаток» противоречит само себе — половина фразы
    # утверждает обратное второй половине.
    note_clean: str
    count: int
    # Что именно нашлось. Без списка переход в раздел показывает страницу,
    # а не проблему: человек приходит и ищет те самые двадцать одну позицию
    # среди пятидесяти четырёх строк.
    items: list[Found]
    # Страница, без доступа к которой сигнал не показывается вовсе.
    page_key: str
    # Куда идти за подробностями — с наложенной сортировкой, а не «в раздел
    # вообще». Насколько точно раздел показывает именно эти строки, зависит
    # от того, есть ли у него нужный разрез; где его нет — это долг раздела,
    # а не повод убирать переход.
    route: str
    # `bad` — уже случилось, `warn` — случится скоро, `ok` — проверено и чисто.
    tone: str


def _tone(count: int, *, serious: bool) -> str:
    if count == 0:
        return "ok"
    return "bad" if serious else "warn"


# Сколько позиций перечислять в списке сигнала. Двадцать — предел, за которым
# список перестаёт быть ответом и становится таблицей; для решения хватает
# крупных, а остальное человек досмотрит в разделе.
LIST_ROWS = 20


def of(*, today: date | None = None) -> list[Signal]:
    """Все проверки разом. Отбор по доступам делает сборка страницы."""
    day = today or local_today()
    # Минус один: обе границы включаются, и без поправки в выборку попадает
    # 61 день, а делится расход на 60 — дневной темп завышался на 1,7 %.
    # То же правило, что у `coverage.days_in`: 1–2 августа — это два дня.
    since = day - timedelta(days=DEMAND_DAYS - 1)

    shipped = within(positions_in(alive(DocumentKind.DEMAND)), since, day)

    goods = list(catalogue.goods())
    goods_left = coverage.by_product(goods, shipped, DEMAND_DAYS)
    by_pk = {product.pk: product for product in goods}

    # «Кончился» — это остаток на нуле **при живом спросе**. Без второго
    # условия сюда попали бы позиции, которых просто никогда не держат
    # на складе, и счётчик перестал бы означать упущенную продажу.
    out_of_stock = [
        (left.per_day, by_pk[pk].name, left.quantity)
        for pk, left in goods_left.items()
        if left.available is not None and left.available <= 0 and left.per_day > 0
    ]
    out_of_stock.sort(reverse=True)

    # Кончившиеся считаются отдельной строкой, поэтому здесь только те,
    # у кого запас ещё есть: иначе одна позиция попала бы в два счётчика,
    # и сумма строк перестала бы сходиться с числом позиций.
    running_out = [
        (left.days_left, by_pk[pk].name, left.available)
        for pk, left in goods_left.items()
        if left.days_left is not None and 0 < left.days_left <= coverage.CRITICAL_DAYS
    ]
    running_out.sort()

    materials_out = _materials_running_out(shipped)

    return [
        Signal(
            key="out-of-stock",
            label="товар кончился",
            label_clean="ходовые товары есть на складе",
            note="спрос есть, остатка нет",
            note_clean="то, что продаётся, есть на складе",
            count=len(out_of_stock),
            items=[
                Found(
                    name=name,
                    note=f"продали {sold:.0f} шт за {DEMAND_DAYS} дней, осталось ноль",
                )
                for _, name, sold in out_of_stock[:LIST_ROWS]
            ],
            page_key="production",
            route="/production",
            tone=_tone(len(out_of_stock), serious=True),
        ),
        Signal(
            key="running-out",
            label=f"хватит меньше чем на {coverage.CRITICAL_DAYS} дней",
            label_clean=f"запаса везде больше чем на {coverage.CRITICAL_DAYS} дней",
            note=f"считая по спросу за {DEMAND_DAYS} дней",
            note_clean=f"считая по спросу за {DEMAND_DAYS} дней",
            count=len(running_out),
            items=[
                Found(
                    name=name,
                    note=f"хватит на {with_plural(days, 'день', 'дня', 'дней')}"
                    + (f", остаток {available:.0f} шт" if available is not None else ""),
                )
                for days, name, available in running_out[:LIST_ROWS]
            ],
            page_key="production",
            route="/production",
            tone=_tone(len(running_out), serious=False),
        ),
        Signal(
            key="materials-out",
            label=f"позиций сырья кончится за {MATERIAL_DAYS} дней",
            label_clean=f"сырья хватает больше чем на {MATERIAL_DAYS} дней",
            note="к сроку расхода добавляется срок поставки",
            note_clean="считая по расходу через техкарты",
            count=len(materials_out),
            items=materials_out[:LIST_ROWS],
            page_key="supplies-materials",
            # Сортировка по запасу: кончающееся встаёт первым. Колонка
            # заведена 04.09 ровно ради этого перехода — до неё страница
            # открывалась по сумме закупки, и восемь позиций приходилось
            # искать глазами среди двухсот.
            route="/supplies/materials?sort=days_left",
            tone=_tone(len(materials_out), serious=False),
        ),
        _at_a_loss(),
        _without_price(),
        _over_reserved(),
    ]


def _materials_running_out(shipped) -> list[Found]:
    """Сколько наименований сырья кончится за месяц.

    **Расход сырья считается через техкарты, а не по отгрузкам.** Сырьё
    не продают: оно уходит, когда из него варят проданный товар. Посчитай
    мы его так же, как готовую продукцию, — по позициям отгрузок, —
    в расход попали бы только те редкие случаи, когда сырьё отгрузили
    как есть, и счётчик показал бы две позиции вместо шести.

    Разворот до сырья — общий с «Материалами в отгрузках»
    (`core/services/consumption.py`), чтобы обе страницы за один день
    называли одно и то же число.
    """
    used = consumption.of_shipments(shipped)
    available = {
        stock.product_id: stock.available
        for stock in Stock.objects.filter(
            product__in=[item.product.pk for item in used.materials]
        )
    }
    rows = []
    for item in used.materials:
        left = coverage.of(item.quantity, DEMAND_DAYS, available.get(item.product.pk))
        if left.days_left is None or left.days_left > MATERIAL_DAYS:
            continue
        rows.append((left.days_left, item.product, left.per_day, left.available))

    rows.sort(key=lambda row: (row[0], row[1].name))

    # Заказ считается пачкой: цены одним запросом, сроки одним проходом
    # по приёмкам. По позиции это было бы два запроса на каждую из восьми.
    orders = restock.of(
        [
            (
                product.pk,
                product.uom.name if product.uom else "",
                per_day,
                stock_left if stock_left is not None else Decimal(0),
                days,
            )
            for days, product, per_day, stock_left in rows
        ]
    )

    found = []
    for days, product, _, _ in rows:
        note = f"хватит на {with_plural(days, 'день', 'дня', 'дней')}"
        order = orders.get(product.pk)
        if order is not None:
            # Тревога без ответа «что делать» отправляет человека собирать
            # недостающее по трём страницам. Сколько, у кого и почём —
            # рядом с самой строкой.
            note = f"{note} · {restock.describe(order)}"
            if order.in_time is False:
                note = f"{note} · не успеваем"
        found.append(Found(name=product.name, note=note))
    return found


def _at_a_loss() -> Signal:
    """Товары, проданные дешевле себестоимости.

    Считается по всей истории, а не за месяц: убыточная цена — свойство
    прайса, а не месяца, и в коротком окне товар с двумя продажами то
    попадает в список, то исчезает из него без единого изменения в учёте.
    """
    # Услуги исключены, как и везде: доставка с себестоимостью выше выручки
    # попала бы в «товары продаются в убыток» и увела бы чинить цену услуги.
    rows = [
        (row["revenue"] - row["cost"], row["product__name"])
        for row in ProfitDay.objects.exclude(product__kind=ProductKind.SERVICE)
        .values("product__name")
        .annotate(revenue=Sum("revenue_kopecks"), cost=Sum("cost_kopecks"))
        .filter(revenue__lt=F("cost"))
        if row["cost"] - row["revenue"] >= MIN_LOSS_KOPECKS
    ]
    rows.sort()
    return Signal(
        key="at-a-loss",
        label="товаров продаются в убыток",
        label_clean="все товары продаются дороже себестоимости",
        note=f"убыток больше {MIN_LOSS_KOPECKS // 100} ₽ за всё время",
        note_clean="сверено с отчётом прибыльности за всё время",
        count=len(rows),
        items=[
            Found(name=name, note=f"убыток {-loss / 100:,.0f} ₽".replace(",", " "))
            for loss, name in rows[:LIST_ROWS]
        ],
        page_key="profitability",
        # Сортировка по марже: убыточные встают первыми, и человек приходит
        # не «на страницу», а к тем самым строкам.
        route="/profitability?sort=margin",
        tone=_tone(len(rows), serious=True),
    )


def _without_price() -> Signal:
    """Товар лежит на складе, а продать его нельзя — цены нет.

    Только с артикулом и только с остатком. Без первого условия сюда
    попало бы 276 позиций сырья, которым цена продажи и не положена;
    без второго — карточки, заведённые впрок, по которым вопроса ещё нет.
    """
    # Отбор товаров — общий (`catalogue.goods`): живые, не архивные, с артикулом.
    # Свой `exclude(article="")` пропускал архивные и удалённые: сигнал звал
    # разбираться с позицией, которой на целевой странице нет вовсе.
    rows = [
        (stock.quantity, stock.product.name)
        for stock in Stock.objects.select_related("product").filter(
            sale_price_kopecks=0, quantity__gt=0, product__in=catalogue.goods()
        )
    ]
    rows.sort(reverse=True)
    return Signal(
        key="without-price",
        label="товара без цены продажи",
        label_clean="у всех товаров на складе есть цена",
        note="лежат на складе, но продать нельзя",
        note_clean="у всех позиций с остатком цена задана",
        count=len(rows),
        items=[
            Found(name=name, note=f"на складе {quantity:.0f} шт")
            for quantity, name in rows[:LIST_ROWS]
        ],
        page_key="shipments-products",
        # Сортировка по цене карточки: «не задана» встаёт первой. Колонка
        # заведена 04.09 ради этого перехода — до неё страница открывалась
        # по выручке, и три позиции терялись среди шестидесяти шести.
        route="/shipments/products?sort=card_price",
        tone=_tone(len(rows), serious=True),
    )


def _over_reserved() -> Signal:
    """Обещано больше, чем есть на складе.

    Сегодня таких нет, и это не повод убирать проверку: резерв появляется
    из галочки в заказе покупателя, а её начали ставить недавно. Пустая
    проверка отвечает «обещано ровно то, что есть» — это ответ, а не молчание.
    """
    # Тот же общий отбор: архивный товар с резервом сверх остатка — это долг
    # по документу, а не задача склада, и на «Расчёте производства» его нет.
    rows = [
        (stock.reserved - stock.quantity, stock.product.name, stock.reserved, stock.quantity)
        for stock in Stock.objects.select_related("product").filter(
            reserved__gt=F("quantity"), product__in=catalogue.goods()
        )
    ]
    rows.sort(reverse=True)
    return Signal(
        key="over-reserved",
        label="заказов нечем закрыть",
        label_clean="остатка хватает на все заказы",
        note="в резерве обещано больше, чем лежит на складе",
        note_clean="всё, что зарезервировано под заказы, есть в наличии",
        count=len(rows),
        items=[
            Found(
                name=name,
                note=f"в резерве {reserved:.0f} при остатке {quantity:.0f} — "
                f"не хватает {short:.0f}",
            )
            for short, name, reserved, quantity in rows[:LIST_ROWS]
        ],
        page_key="production",
        # Резерв показан в строке «Расчёта производства» с 04.09 — до этого
        # переход вёл на страницу, где превышение не было видно вовсе.
        route="/production",
        tone=_tone(len(rows), serious=True),
    )


@dataclass(frozen=True)
class SyncTrouble:
    """Что именно отстало и насколько. `None` — всё идёт по расписанию."""

    kind: str
    # Что устарело — словами человека, а не именем сущности. «Синхронизация
    # „остатки и себестоимость“» — это внутреннее название, и владелец
    # справедливо о него споткнулся: непонятно ни что сломалось, ни чем
    # это грозит.
    label: str
    # Как часто это обычно обновляется. Без нормы «молчит 2 часа» ничего
    # не значит: для остатков это восемь пропущенных прогонов, для документов
    # — половина обычного перерыва.
    usual: str
    # Чему верить нельзя, пока не обновится, — законченным предложением.
    # Кусок фразы («что лежит на складе») на фронте пришлось бы согласовывать
    # с окружающим текстом, и получалось «могли измениться что лежит».
    affects: str
    hours: int


def sync_trouble(*, now: datetime | None = None) -> SyncTrouble | None:
    """Синхронизация не отработала — единственный сигнал без своей страницы.

    Он про саму систему, а не про учёт, и виден каждому вошедшему: кнопка
    «Обновить» тоже у всех. В список проверок не входит намеренно — пока
    всё идёт, о нём говорит отметка «данные на 10:17» в шапке, и зелёная
    строка «синхронизация в порядке» повторяла бы её впустую.
    """
    moment = now or timezone.now()
    for kind, label, usual, affects, limit in (
        (
            SyncKind.STATE,
            "Остатки на складе",
            "каждые 15 минут",
            "Сколько чего лежит и на сколько этого хватит — могло измениться.",
            STATE_STALE_HOURS,
        ),
        (
            SyncKind.DOCUMENTS,
            "Отгрузки и продажи",
            "раз в сутки ночью",
            "Выручка, маржа и всё, что считается по документам, — могли устареть.",
            DOCUMENTS_STALE_HOURS,
        ),
    ):
        last = freshness.last_success(kind)
        if last is None:
            return SyncTrouble(
                kind=kind, label=label, usual=usual, affects=affects, hours=-1
            )
        hours = int((moment - last).total_seconds() // 3600)
        if hours >= limit:
            return SyncTrouble(
                kind=kind, label=label, usual=usual, affects=affects, hours=hours
            )
    return None


def known() -> bool:
    """Есть ли вообще с чем работать.

    Третье состояние блока: до первого успешного синка все счётчики равны
    нулю, и «всё в порядке» на пустой базе — самая дорогая ложь на странице.
    """
    return freshness.stock_synced_at() is not None
