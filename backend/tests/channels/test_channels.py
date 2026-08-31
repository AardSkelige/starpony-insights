"""Строки страницы «Каналы продаж»: что складывается, а что нет.

Класс ошибок, который здесь стерегут, за три сессии встречался пять раз:
соседние числа оказываются о разных множествах. Поиск сужает строки,
но не имеет права трогать знаменатель доли; отгрузка без канала не строка,
но обязана остаться в сводке; покупателей нельзя сложить по колонке.
Ни одна такая ошибка не падает и не выглядит подозрительно на экране.
"""

from datetime import date

import pytest

from api.channels.services import breakdown, channels as service
from tests.channels.conftest import moscow, position


@pytest.fixture
def three_channels(db, make_channel, make_demand, make_buyer, make_product):
    """Три канала с разной механикой — как на боевых данных.

    «Витрина» берёт чеком: две отгрузки на 500 000 копеек.
    «Маркет» берёт числом: четыре по 50 000.
    «Соцсеть» раздаёт: две отгрузки даром.
    """
    shop = make_channel("Витрина")
    market = make_channel("Маркет")
    social = make_channel("Соцсеть")

    goods = make_product("Репеллент 500 мл")
    club = make_buyer("КСЦ «Каприоль»")

    for _ in range(2):
        demand = make_demand(sales_channel=shop, agent=club, total_kopecks=500_000)
        position(demand, goods, 1, 500_000)
    for _ in range(4):
        demand = make_demand(sales_channel=market, total_kopecks=50_000)
        position(demand, goods, 1, 50_000)
    for _ in range(2):
        make_demand(sales_channel=social, total_kopecks=0)

    return shop, market, social


def rows_by_name(filters=None):
    whole = service.prepared(filters or service.Filters())
    return {row["name"]: row for row in whole["rows"]}, whole


def test_revenue_comes_from_the_document(three_channels):
    """Выручка складывается из сумм документов, а не из строк.

    Позиции сходятся с суммой документа сегодня и перестанут сходиться
    ровно тогда, когда синхронизация пропустит позицию. Сумма документа
    остаётся фактом учёта, и брать надо её.
    """
    rows, _ = rows_by_name()

    assert rows["Витрина"]["revenue_kopecks"] == 1_000_000
    assert rows["Маркет"]["revenue_kopecks"] == 200_000
    assert rows["Соцсеть"]["revenue_kopecks"] == 0


def test_money_and_count_disagree(three_channels):
    """Главный вопрос страницы: деньги и число отгрузок расходятся.

    У «Витрины» 2 отгрузки из 8 и 83 % выручки, у «Маркета» половина
    отгрузок и шестая часть денег. Обе колонки обязаны стоять рядом
    и считаться по одной выборке.
    """
    rows, _ = rows_by_name()

    assert rows["Витрина"]["shipments_count"] == 2
    assert rows["Маркет"]["shipments_count"] == 4
    assert round(float(rows["Витрина"]["revenue_share"]), 4) == 0.8333
    assert round(float(rows["Маркет"]["revenue_share"]), 4) == 0.1667


def test_search_narrows_rows_but_not_the_denominator(three_channels):
    """Поиск сужает показанное, но не то, от чего считается доля.

    Иначе после поиска «маркет» его доля показала бы 100 %, хотя на него
    приходится шестая часть продаж. Пять дефектов этого класса за три
    сессии — все выглядели обычными числами.
    """
    rows, whole = rows_by_name(service.Filters(search="маркет"))

    assert list(rows) == ["Маркет"]
    assert round(float(rows["Маркет"]["revenue_share"]), 4) == 0.1667
    assert whole["totals"]["revenue_kopecks"] == 200_000
    assert whole["coverage"]["revenue_kopecks"] == 1_200_000


def test_totals_add_up_to_the_column(three_channels):
    """Итог под таблицей обязан сходиться со сложением колонки."""
    _, whole = rows_by_name()

    assert whole["totals"]["revenue_kopecks"] == sum(
        row["revenue_kopecks"] for row in whole["rows"]
    )
    assert whole["totals"]["shipments_count"] == sum(
        row["shipments_count"] for row in whole["rows"]
    )


def test_buyers_are_united_not_summed(three_channels, make_demand):
    """Покупателей нельзя сложить по колонке: один приходит через несколько
    каналов и был бы посчитан дважды.

    В фикстуре клуб покупает через «Витрину», здесь он же покупает через
    «Маркет» — покупателей в итоге должно стать не больше, чем людей.
    """
    from core.models import Counterparty

    _, market, _ = three_channels
    caprioll = Counterparty.objects.get(name="КСЦ «Каприоль»")
    make_demand(sales_channel=market, agent=caprioll, total_kopecks=10_000)

    _, whole = rows_by_name()
    by_column = sum(row["buyers_count"] for row in whole["rows"])

    assert whole["totals"]["buyers_count"] < by_column


def test_shipment_without_channel_is_not_a_row_but_stays_in_coverage(
    three_channels, make_demand
):
    """Отгрузка без канала строкой не становится — канала, к которому её
    отнести, в учёте нет. Но в сводке она обязана быть: иначе итог таблицы
    молча разойдётся с учётом, и объяснить расхождение будет нечем.
    """
    make_demand(sales_channel=None, total_kopecks=70_000)

    rows, whole = rows_by_name()

    assert len(rows) == 3
    assert whole["totals"]["shipments_count"] == 8
    assert whole["coverage"]["shipments_count"] == 9
    assert whole["coverage"]["unassigned_shipments_count"] == 1
    assert whole["coverage"]["unassigned_revenue_kopecks"] == 70_000


def test_draft_and_deleted_shipments_are_out(three_channels, make_demand):
    """Черновик и удалённый документ не считаются проданным.

    Сейчас таких в аккаунте нет ни одного, и именно поэтому проверка нужна
    сегодня: когда появится первый, расхождение с учётом никто не заметит.
    """
    make_demand(total_kopecks=999_999, applicable=False)
    make_demand(total_kopecks=888_888, deleted=True)

    _, whole = rows_by_name()

    assert whole["coverage"]["revenue_kopecks"] == 1_200_000


def test_period_narrows_the_selection(three_channels, make_demand):
    """Период сужает то, что посчитано, — в отличие от поиска."""
    make_demand(moment=moscow(2026, 7, 4), total_kopecks=300_000)

    _, whole = rows_by_name(
        service.Filters(date_from=date(2026, 7, 1), date_to=date(2026, 7, 31))
    )

    assert whole["coverage"]["revenue_kopecks"] == 300_000


def test_rows_without_a_cheque_stay_at_the_bottom(
    three_channels, make_channel, make_demand, db
):
    """Строки, которым сортировать нечем, всегда внизу — в обе стороны.

    Канал, по которому в периоде не продавали, чека не имеет. Уйди он
    в общий ключ, список «где чек крупнее» начинался бы с каналов,
    где не продавали вовсе.
    """
    quiet = make_channel("Молчун")
    make_demand(sales_channel=quiet, moment=moscow(2026, 7, 4))

    filters = service.Filters(date_from=date(2026, 5, 1), date_to=date(2026, 5, 31))
    down = [row["name"] for row in service.prepared(filters)["rows"]]

    filters = service.Filters(
        date_from=date(2026, 5, 1), date_to=date(2026, 5, 31), ordering="receipt"
    )
    up = [row["name"] for row in service.prepared(filters)["rows"]]

    # «Молчун» в периоде не продавал: в таблицу он не попадает вовсе,
    # а порядок остальных переворачивается целиком.
    assert down == list(reversed(up))


def test_top_buyers_keep_the_tail(
    three_channels, make_channel, make_demand, make_buyer
):
    """Хвост списка сворачивается, но не выбрасывается: слагаемые обязаны
    складываться в выручку канала.

    Покупатели здесь **разные**: с одним и тем же список свернуть нечего,
    и проверка прошла бы вхолостую при любом коде.
    """
    crowd = make_channel("Толпа")
    for index in range(8):
        make_demand(
            sales_channel=crowd,
            agent=make_buyer(f"Покупатель {index}"),
            total_kopecks=(index + 1) * 1_000,
        )

    rows, _ = rows_by_name()
    buyers = rows["Толпа"]["buyers"]

    assert len(buyers["items"]) == breakdown.LIMIT
    assert buyers["rest_count"] == 3

    shown = sum(item["revenue_kopecks"] for item in buyers["items"])
    assert shown + buyers["rest_revenue_kopecks"] == rows["Толпа"]["revenue_kopecks"]


def test_standings_ignore_search_and_paging(three_channels):
    """Полосы над таблицей описывают выборку, а не найденное.

    Поиск сужает таблицу — он про «что показано». Полосы отвечают на «кому
    уходят деньги у нас», и оставь мы в них найденное, единственная строка
    заняла бы всю ширину со стопроцентной долей.
    """
    whole = service.prepared(service.Filters(search="маркет", page_size=1))
    names = [item["name"] for item in whole["standings"]]

    assert names == ["Витрина", "Маркет", "Соцсеть"]
    assert sum(float(item["shipments_share"]) for item in whole["standings"]) == 1.0


def test_standings_compare_two_shares_of_one_set(three_channels):
    """Обе доли считаются от одного множества: сравнивать иначе бессмысленно,
    а выглядит это обычным числом."""
    whole = service.prepared(service.Filters())
    by_name = {item["name"]: item for item in whole["standings"]}

    # «Витрина» берёт чеком: четверть отгрузок и пять шестых денег.
    assert round(float(by_name["Витрина"]["shipments_share"]), 3) == 0.25
    assert round(float(by_name["Витрина"]["revenue_share"]), 3) == 0.833
    # «Маркет» — наоборот: половина отгрузок и шестая часть денег.
    assert round(float(by_name["Маркет"]["shipments_share"]), 3) == 0.5
    assert round(float(by_name["Маркет"]["revenue_share"]), 3) == 0.167
