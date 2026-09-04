"""Окно главной: последний полный месяц.

Ошибка здесь тихая и ровно в один месяц: страница показала бы «сентябрь
против августа» четвёртого числа и объявила падение на 90 % там, где ничего
не случилось.
"""

from datetime import date

from api.home.services.period import month_of, window

pytestmark = []


def test_current_month_is_the_last_complete_one():
    """Четвёртого сентября итоги подводятся по августу, а не по сентябрю."""
    result = window(date(2026, 9, 4))

    assert (result.current.first, result.current.last) == (date(2026, 8, 1), date(2026, 8, 31))
    assert result.current.label == "Август 2026"
    assert result.current.label_of == "августа 2026"


def test_compares_against_the_month_before():
    result = window(date(2026, 9, 4))

    assert (result.earlier.first, result.earlier.last) == (date(2026, 7, 1), date(2026, 7, 31))


def test_running_month_is_reported_separately():
    """Идущий месяц виден, но отдельно: его показывают бледным столбиком."""
    result = window(date(2026, 9, 4))

    assert result.running is not None
    assert result.running.label == "Сентябрь 2026"
    assert result.running_days == 4
    assert result.running.days == 30


def test_first_day_has_no_running_month():
    """Первого числа идущего месяца ещё нет: один день — не столбик.

    Показать «1 из 31» значило бы объявить провал в день, когда месяц
    не начался.
    """
    result = window(date(2026, 9, 1))

    assert result.running is None
    assert result.current.label == "Август 2026"
    assert result.current.label_of == "августа 2026"


def test_january_looks_back_into_last_year():
    """Через новый год: январь сравнивается с декабрём прошлого.

    Арифметика по числу дней ошибается именно здесь, и ошибка выглядит
    правдоподобно — просто месяц не тот.
    """
    result = window(date(2027, 1, 15))

    assert result.current.label == "Декабрь 2026"
    assert result.earlier.label == "Ноябрь 2026"
    # Дательный — для сравнения «Декабрь к ноябрю».
    assert result.earlier.label_to == "ноябрю 2026"


def test_february_ends_on_its_own_last_day():
    """Февраль високосного года кончается 29-м, а не 28-м или 30-м."""
    assert month_of(date(2028, 2, 10)).last == date(2028, 2, 29)
    assert month_of(date(2026, 2, 10)).last == date(2026, 2, 28)
