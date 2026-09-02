"""Сборка страницы «Сроки оплаты»: три суммы, старение, доли, поиск.

Все проверки здесь про одну болезнь — смешение множеств. Долг покупателя,
расчёты через площадку и товар на реализации приходят из одного места
учёта, «отгружено и не оплачено», и складываются в число, которое выглядит
правдой: на боевых данных 890 210 ₽ «долга», из которых нам должны 123 044 ₽.
"""

import pytest

from api.deadlines.services import deadlines as service
from api.deadlines.services.aging import AgeBucket
from core.models import ContractType, DocumentKind
from core.services.payment_deadline import DebtGroup

pytestmark = pytest.mark.django_db


@pytest.fixture
def three_debtors(make_agent, make_document, make_channel):
    """Покупатель, площадка и комиссионер — три природы одного «не оплачено»."""
    buyer = make_agent("ООО «ПМТ»")
    ozon = make_agent("ООО «Интернет Решения»", tags=["маркетплейсы"])
    quiet = make_agent("ИП Полковникова")

    smart = make_channel("ХорсСмарт")
    marketplace = make_channel("Озон")

    make_document(agent=buyer, age_days=5, total_kopecks=100_000, sales_channel=smart)
    make_document(agent=buyer, age_days=56, total_kopecks=200_000, sales_channel=smart)
    make_document(
        agent=ozon, age_days=20, total_kopecks=900_000, sales_channel=marketplace
    )
    make_document(agent=quiet, age_days=70, total_kopecks=50_000)

    return {"buyer": buyer, "ozon": ozon, "quiet": quiet}


def rows_by_name(payload) -> dict:
    return {row["name"]: row for row in payload["rows"]}


class TestRows:
    def test_row_is_a_counterparty_not_a_document(self, three_debtors):
        """Строка — контрагент, а не бумага.

        У Озона 150 неоплаченных отгрузок на боевых данных; список из них
        отвечает на вопрос «какие документы висят», которого не задают.
        """
        rows = rows_by_name(service.prepared(service.Filters()))

        assert rows["ООО «ПМТ»"]["documents_count"] == 2
        assert rows["ООО «ПМТ»"]["debt_kopecks"] == 300_000

    def test_oldest_and_newest_bound_the_row(self, three_debtors):
        """Возраст старейшего — то, по чему решают, звонить ли сегодня.

        Медиана здесь не годится: платить заставляет самый застарелый долг,
        а не типичный.
        """
        row = rows_by_name(service.prepared(service.Filters()))["ООО «ПМТ»"]

        assert row["oldest_age_days"] == 56
        assert row["newest_age_days"] == 5

    def test_channels_come_from_the_documents(self, three_debtors):
        row = rows_by_name(service.prepared(service.Filters()))["ООО «ПМТ»"]
        assert row["channels"] == ["ХорсСмарт"]

    def test_kinds_explain_what_made_the_debt(
        self, make_agent, make_document, make_contract
    ):
        """Долг Каприоля — два отчёта комиссионера, а не отгрузки.

        Без этого «2 документа на 98 125 ₽» рядом с шестнадцатью отгрузками
        в разборе выглядит ошибкой расчёта.
        """
        agent = make_agent("КРМОО «Каприоль»")
        contract = make_contract(agent)
        make_document(agent=agent, kind=DocumentKind.COMMISSION_REPORT, contract=contract)
        make_document(agent=agent, kind=DocumentKind.DEMAND, contract=contract)

        row = rows_by_name(service.prepared(service.Filters()))["КРМОО «Каприоль»"]

        assert row["kinds"] == {DocumentKind.COMMISSION_REPORT: 1}
        assert row["documents_count"] == 1

    def test_row_carries_its_own_aging(self, three_debtors):
        """Распределение внутри строки: 150 отгрузок одного месяца и 22,
        растянутые на три, — разные новости при одинаковой сумме."""
        row = rows_by_name(service.prepared(service.Filters()))["ООО «ПМТ»"]
        shelves = {shelf["key"]: shelf for shelf in row["aging"]}

        assert shelves[AgeBucket.FRESH]["debt_kopecks"] == 100_000
        assert shelves[AgeBucket.STALE]["debt_kopecks"] == 200_000


class TestMarketplaces:
    def test_marketplace_leaves_the_receivables(self, three_debtors):
        """Площадка живёт отдельно от долга.

        Выплата приходит реестром раз в цикл и в учёт не заводится вовсе:
        у «Интернет Решений» ни одного платежа на 236 235 ₽ отгрузок.
        Считать это долгом наравне с покупателем — значит утопить настоящую
        дебиторку вчетверо большей суммой.
        """
        whole = service.prepared(service.Filters())

        assert [row["name"] for row in whole["marketplaces"]] == [
            "ООО «Интернет Решения»"
        ]
        assert "ООО «Интернет Решения»" not in rows_by_name(whole)
        assert whole["totals"]["debt_kopecks"] == 350_000

    def test_tag_is_read_case_insensitively(self, make_agent, make_document):
        """Группу набирает человек: «Маркетплейсы» — та же группа."""
        agent = make_agent("ООО «Яндекс.Маркет»", tags=[" Маркетплейсы "])
        make_document(agent=agent)

        whole = service.prepared(service.Filters())

        assert [row["name"] for row in whole["marketplaces"]] == ["ООО «Яндекс.Маркет»"]

    def test_marketplace_shares_stay_inside_marketplaces(self, three_debtors):
        """Доля площадки считается среди площадок.

        Положи её рядом с дебиторкой — и сумма долей на экране перевалила бы
        за сто процентов, не подав ни одного признака.
        """
        whole = service.prepared(service.Filters())

        assert whole["marketplaces"][0]["debt_share"] == 1
        assert sum(row["debt_share"] for row in whole["rows"]) == 1


class TestConsignment:
    def test_commission_shipment_is_not_a_debt(
        self, make_agent, make_document, make_contract
    ):
        """Товар по договору комиссии ушёл на реализацию.

        `payedSum` у такой отгрузки не заполняется никогда, а деньги приходят
        отчётом комиссионера — он в долг уже включён. Посчитать оба значило бы
        посчитать один и тот же товар дважды.
        """
        agent = make_agent("КРМОО «Каприоль»")
        contract = make_contract(agent)
        make_document(agent=agent, contract=contract, total_kopecks=400_000)
        make_document(
            agent=agent,
            kind=DocumentKind.COMMISSION_REPORT,
            contract=contract,
            total_kopecks=80_000,
        )

        whole = service.prepared(service.Filters())
        row = rows_by_name(whole)["КРМОО «Каприоль»"]

        assert row["debt_kopecks"] == 80_000
        assert whole["coverage"]["consignment_kopecks"] == 400_000
        assert whole["coverage"]["consignment_count"] == 1

    def test_sales_contract_does_not_hide_the_debt(
        self, make_agent, make_document, make_contract
    ):
        """Договор купли-продажи — обычная продажа, и долг по ней настоящий."""
        agent = make_agent("ООО «Ревада-Нева»")
        contract = make_contract(agent, contract_type=ContractType.SALES)
        make_document(agent=agent, contract=contract, total_kopecks=300_000)

        whole = service.prepared(service.Filters())

        assert rows_by_name(whole)["ООО «Ревада-Нева»"]["debt_kopecks"] == 300_000
        assert whole["coverage"]["consignment_kopecks"] == 0


class TestSearch:
    def test_search_narrows_rows(self, three_debtors):
        whole = service.prepared(service.Filters(search="пмт"))
        assert [row["name"] for row in whole["rows"]] == ["ООО «ПМТ»"]

    def test_share_denominator_is_not_narrowed_by_search(self, three_debtors):
        """Доля строки считается от всей дебиторки, а не от найденного.

        Иначе, отыскав «пмт», человек увидел бы у него 100 % — при том,
        что на него приходится восемьдесят шесть сотых.
        """
        found = rows_by_name(service.prepared(service.Filters(search="пмт")))

        assert found["ООО «ПМТ»"]["debt_share"] < 1
        assert found["ООО «ПМТ»"]["debt_share"] == service.share(300_000, 350_000)

    def test_totals_follow_the_search(self, three_debtors):
        """Итог под таблицей обязан сходиться со сложением её колонки."""
        totals = service.prepared(service.Filters(search="пмт"))["totals"]

        assert totals["counterparties_count"] == 1
        assert totals["debt_kopecks"] == 300_000
        assert totals["oldest_age_days"] == 56

    def test_coverage_ignores_the_search(self, three_debtors):
        """Сводка — про всю картину: она отвечает на «полное ли число»."""
        coverage = service.prepared(service.Filters(search="пмт"))["coverage"]

        assert coverage["counterparties_count"] == 2
        assert coverage["debt_kopecks"] == 350_000
        assert coverage["marketplace_kopecks"] == 900_000

    def test_aging_describes_the_same_rows_as_the_table(self, three_debtors):
        """График старения — про то же, что таблица под ним.

        Покажи он всю дебиторку при поиске «пмт», столбики описывали бы
        не найденное, ничем этого не выдав.
        """
        whole = service.prepared(service.Filters(search="пмт"))
        shelves = {shelf["key"]: shelf for shelf in whole["aging"]}

        assert shelves[AgeBucket.FRESH]["debt_kopecks"] == 100_000
        assert shelves[AgeBucket.STALE]["debt_kopecks"] == 200_000
        assert shelves[AgeBucket.OLD]["debt_kopecks"] == 0


class TestOrderAndPaging:
    def test_default_order_is_the_biggest_debt(self, three_debtors):
        whole = service.prepared(service.Filters())
        assert [row["name"] for row in whole["rows"]] == [
            "ООО «ПМТ»",
            "ИП Полковникова",
        ]

    def test_order_by_oldest(self, three_debtors):
        whole = service.prepared(service.Filters(ordering="-oldest"))
        assert [row["name"] for row in whole["rows"]] == [
            "ИП Полковникова",
            "ООО «ПМТ»",
        ]

    def test_unknown_ordering_falls_back(self, three_debtors):
        """Ссылка со страницы соседа не должна ронять эту.

        У «Товаров» порядок `-revenue`, и такого ключа здесь нет вовсе.
        """
        whole = service.prepared(service.Filters(ordering="-revenue"))
        assert [row["name"] for row in whole["rows"]] == [
            "ООО «ПМТ»",
            "ИП Полковникова",
        ]

    def test_page_cuts_rows_but_not_totals(self, three_debtors):
        page = service.page(service.Filters(page_size=1))

        assert len(page["results"]) == 1
        assert page["count"] == 2
        assert page["totals"]["debt_kopecks"] == 350_000


class TestOverdue:
    """Срок оплаты: группы включаются сами, как только появится отсрочка.

    Сегодня они пусты — отсрочка не задана ни у одного из 107 контрагентов, —
    и в этом весь смысл проверки: механизм обязан работать до того, как
    владелец заполнит поле, а не после того, как кто-то заметит, что он молчит.
    """

    def test_groups_are_empty_while_no_deferral_is_set(self, three_debtors):
        coverage = service.prepared(service.Filters())["coverage"]

        assert coverage["overdue_kopecks"] == 0
        assert coverage["soon_kopecks"] == 0
        assert coverage["with_deferral_count"] == 0

    def test_deferral_turns_the_groups_on(self, make_agent, make_document):
        """Отсрочка появилась — появились и просрочка, и «скоро истекает»."""
        agent = make_agent("ООО «ПМТ»", deferral_days=14)
        # 40 дней назад при отсрочке 14 — просрочено на 26 дней.
        make_document(agent=agent, age_days=40, total_kopecks=300_000)
        # 12 дней назад — срок через два дня, это «скоро истекает» (порог 3).
        make_document(agent=agent, age_days=12, total_kopecks=100_000)
        # Вчерашняя отгрузка — до срока далеко.
        make_document(agent=agent, age_days=1, total_kopecks=50_000)

        whole = service.prepared(service.Filters())
        coverage = whole["coverage"]

        assert coverage["overdue_count"] == 1
        assert coverage["overdue_kopecks"] == 300_000
        assert coverage["soon_count"] == 1
        assert coverage["soon_kopecks"] == 100_000

    def test_row_groups_add_up_to_the_coverage(self, make_agent, make_document):
        """Итог сводки складывается из тех же групп, что показывает строка.

        Отдельный запрос описывал бы другое множество, и число в сводке
        разошлось бы с суммой по строкам — тихо.
        """
        first = make_agent("Первый", deferral_days=5)
        second = make_agent("Второй", deferral_days=5)
        make_document(agent=first, age_days=30, total_kopecks=100_000)
        make_document(agent=second, age_days=30, total_kopecks=200_000)

        whole = service.prepared(service.Filters())
        by_rows = sum(
            entry["debt_kopecks"]
            for row in whole["rows"]
            for entry in row["groups"]
            if entry["key"] == DebtGroup.OVERDUE
        )

        assert by_rows == whole["coverage"]["overdue_kopecks"] == 300_000

    def test_marketplaces_stay_out_of_the_overdue_total(
        self, make_agent, make_document
    ):
        """Просрочка считается по дебиторке, а не по всему неоплаченному.

        Площадка не нарушает срок — у неё его нет: выплата приходит реестром
        и в учёт не заводится. Попади она в это число, «просрочено» на экране
        описывало бы то, по чему нельзя позвонить.
        """
        ozon = make_agent("Озон", deferral_days=5, tags=["маркетплейсы"])
        make_document(agent=ozon, age_days=60, total_kopecks=900_000)

        coverage = service.prepared(service.Filters())["coverage"]

        assert coverage["overdue_kopecks"] == 0
