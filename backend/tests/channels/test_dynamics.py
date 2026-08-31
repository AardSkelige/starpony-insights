"""Стопка по каналам во времени: корзины, свёртка и местный календарь.

Три тихие ошибки стерегутся здесь. Разный шаг у стопки и у ряда в разборе
строки — два графика рядом читаются как разные периоды. Выброшенный хвост —
слагаемые перестают складываться в высоту столбика. UTC вместо московского
календаря — ночная отгрузка уезжает в предыдущие сутки, и крайний столбик
выпадает вместе со своими деньгами.
"""

from datetime import date

from api.channels.services import channels as service, dynamics, palette
from tests.channels.conftest import moscow


def build(filters=None):
    whole = service.prepared(filters or service.Filters())
    return whole["dynamics"], whole["rows"]


def test_stack_and_row_share_one_scale(db, make_channel, make_demand):
    """У стопки и у ряда отдельного канала корзины одни.

    Разойдись они — «канал вырос» на разборе строки означало бы всего лишь
    другой шаг сетки, и сравнить два графика было бы нельзя.
    """
    other = make_channel("Второй")
    make_demand(moment=moscow(2026, 5, 4), total_kopecks=100_000)
    make_demand(sales_channel=other, moment=moscow(2026, 5, 6), total_kopecks=50_000)

    line, rows = build()

    assert len(line.points) == len(rows[0]["dynamics"])
    assert all(len(row["dynamics"]) == len(line.points) for row in rows)


def test_empty_buckets_are_zero_not_missing(db, make_demand):
    """Промежуток без продаж — факт, а не отсутствие данных.

    Выброси его, и провал в спросе превратится в непрерывный ряд,
    где ничего не случилось.
    """
    make_demand(moment=moscow(2026, 5, 4), total_kopecks=100_000)
    make_demand(moment=moscow(2026, 5, 20), total_kopecks=100_000)

    line, _ = build()
    totals = [sum(point["values"]) for point in line.points]

    assert 0 in totals
    assert sum(totals) == 200_000


def test_ninth_channel_folds_into_other(db, make_channel, make_demand):
    """Каналов больше пяти — хвост сворачивается в «Другое», а не получает
    шестой оттенок. Свёрнутое не выбрасывается: столбик обязан оставаться
    равным сумме своих слагаемых."""
    for index in range(7):
        channel = make_channel(f"Канал {index}")
        make_demand(sales_channel=channel, total_kopecks=(index + 1) * 10_000)

    line, _ = build()

    assert len(line.series) == dynamics.NAMED + 1
    assert line.series[-1]["name"] == dynamics.OTHER
    assert line.series[-1]["slot"] is None
    assert sum(sum(point["values"]) for point in line.points) == sum(
        (index + 1) * 10_000 for index in range(7)
    )


def test_shipment_without_channel_goes_to_other(db, make_demand):
    """Отгрузка без канала уходит в «Другое»: отдельной серией она обещала бы
    канал, которого в учёте нет, — а деньги по ней настоящие."""
    make_demand(total_kopecks=100_000)
    make_demand(sales_channel=None, total_kopecks=70_000)

    line, _ = build()

    assert [item["name"] for item in line.series][-1] == dynamics.OTHER
    assert sum(sum(point["values"]) for point in line.points) == 170_000


def test_night_shipment_keeps_its_local_day(db, make_demand):
    """День берётся по московскому календарю, а не по UTC.

    Отгрузка в час ночи по Москве в UTC числится предыдущими сутками.
    Считай мы границы ряда по UTC, последняя корзина оказалась бы за краем
    цикла, и её деньги исчезли бы из графика целиком.
    """
    make_demand(moment=moscow(2026, 5, 4), total_kopecks=100_000)
    make_demand(moment=moscow(2026, 5, 31, hour=1), total_kopecks=70_000)

    line, _ = build()

    assert line.points[-1]["end"] >= date(2026, 5, 31)
    assert sum(sum(point["values"]) for point in line.points) == 170_000


def test_step_follows_the_period(db, make_demand):
    """Шаг подбирается под длину периода — теми же порогами, что у соседней
    страницы: пять месяцев по дням это полторы сотни столбиков в пиксель."""
    make_demand(moment=moscow(2026, 5, 4))
    make_demand(moment=moscow(2026, 5, 20))

    short, _ = build(service.Filters(date_from=date(2026, 5, 1), date_to=date(2026, 5, 20)))
    long, _ = build(service.Filters(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31)))

    assert short.step == "day"
    assert long.step == "month"


def test_colour_is_fixed_to_the_channel_not_to_its_place(db, make_channel, make_demand):
    """Слот закреплён за каналом по всей истории, а не по текущему периоду.

    Возьми мы номер из сортировки — смена периода перекрашивала бы каналы,
    и два графика на одном экране рассказывали бы про разное одним цветом.
    """
    big, small = make_channel("Крупный"), make_channel("Мелкий")
    make_demand(sales_channel=big, moment=moscow(2026, 5, 4), total_kopecks=900_000)
    make_demand(sales_channel=small, moment=moscow(2026, 7, 4), total_kopecks=10_000)

    everywhere = palette.slots()
    july = service.prepared(
        service.Filters(date_from=date(2026, 7, 1), date_to=date(2026, 7, 31))
    )["rows"]

    # В июле продавал только «Мелкий» — и остался при своём слоте,
    # а не занял первый, освободившийся в этом периоде.
    assert [row["name"] for row in july] == ["Мелкий"]
    assert july[0]["slot"] == everywhere[small.id]
    assert everywhere[big.id] == 1


def test_channels_beyond_the_palette_have_no_slot(db, make_channel, make_demand):
    """Слотов восемь. Девятый канал получает `null` и рисуется приглушённым:
    повторить цвет значило бы сказать «это тот же канал»."""
    for index in range(9):
        channel = make_channel(f"Канал {index}")
        make_demand(sales_channel=channel, total_kopecks=(index + 1) * 10_000)

    slots = palette.slots()

    assert len(slots) == palette.SLOTS
    assert sorted(slots.values()) == list(range(1, palette.SLOTS + 1))
