"""Средний чек канала: медиана, её разброс и два разных ноля.

Ошибки здесь тихие. Среднее вместо медианы не падает и не выглядит
подозрительно — оно просто описывает канал, которого нет: у «Точки продаж»
одна отгрузка на 99 495 ₽ поднимает среднее с 2 772 до 13 766 ₽.
"""

from types import SimpleNamespace

from api.channels.services import receipt


def shipments(*amounts):
    """Отгрузки описываются одной суммой: чек больше ничего не спрашивает."""
    return [SimpleNamespace(total_kopecks=amount) for amount in amounts]


def test_median_ignores_the_outlier():
    """Медиана отвечает на «сколько обычно», среднее — нет.

    Числа взяты из боевого канала «Точка продаж»: четыре обычные отгрузки
    и одна крупная. Среднее уезжает втрое, медиана остаётся на месте.
    """
    cheque = receipt.of(shipments(100_000, 200_000, 300_000, 400_000, 9_949_550))

    assert cheque.kopecks == 300_000
    assert cheque.average_kopecks == 2_189_910
    assert cheque.shipments == 5


def test_spread_comes_with_the_median():
    """Разброс приходит рядом всегда: без него медиана молчит о том,
    существует ли описанная ею середина."""
    cheque = receipt.of(shipments(0, 500_000, 2_619_000))

    assert cheque.kopecks == 500_000
    assert cheque.min_kopecks == 0
    assert cheque.max_kopecks == 2_619_000


def test_zero_median_is_an_answer():
    """Ноль — факт учёта, а не пробел.

    У Instagram и Telegram больше половины отгрузок ушли даром, и медиана
    честно равна нулю. Подменить её прочерком значило бы соврать: канал
    работает, просто не продаёт.
    """
    cheque = receipt.of(shipments(0, 0, 0, 597_000, 100_000))

    assert cheque.kopecks == 0
    assert cheque.free_shipments == 3
    assert cheque.shipments == 5


def test_no_shipments_is_a_dash():
    """А вот отсутствие отгрузок — прочерк. Ноль здесь читался бы
    как «продавали и не выручили», а не продавали вовсе."""
    cheque = receipt.of([])

    assert cheque.kopecks is None
    assert cheque.min_kopecks is None
    assert cheque.average_kopecks is None
    assert cheque.shipments == 0


def test_even_count_median_stays_whole_kopecks():
    """Медиана чётного числа отгрузок — среднее двух средних, и половина
    копейки здесь настоящая.

    На экран она уходит целой: дробной копейки в учёте не бывает, и показать
    её значило бы показать величину, которой нет. Половина округляется
    к чётному — так же, как считает `round` во всём остальном проекте.
    """
    cheque = receipt.of(shipments(100_001, 100_002))

    assert cheque.kopecks == 100_002
    assert isinstance(cheque.kopecks, int)
    assert isinstance(cheque.average_kopecks, int)
