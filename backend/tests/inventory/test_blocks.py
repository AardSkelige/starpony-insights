"""Блоки под таблицей: что не считали, где не сходится, что расходится всегда.

Проверяется то, что ломается тихо: папка без единого пересчёта, выпавшая
из списка ровно потому, что в ней нечего показать; блок, считающий деньги
по всей истории, когда таблица считает по последнему пересчёту.
"""

from decimal import Decimal

import pytest

from api.inventory.services import blocks, selection
from api.inventory.services import inventory as service
from tests.inventory.conftest import moscow

pytestmark = pytest.mark.django_db


def rows_of(**filters):
    return service.prepared(selection.Filters(**filters))["rows"]


class TestCoverage:
    def test_folder_without_a_single_count_stays_in_the_list(self, make_product):
        """Папка, которую не открывали, — это и есть ответ блока.

        Выпади она из списка потому, что показывать в ней нечего, вопрос
        «что не считали» остался бы без главной своей строки: на боевых
        данных «Производство/Тара» — 0 из 27.
        """
        make_product("Банка", folder="Производство/Тара")

        items = blocks.coverage(rows_of())["items"]

        assert [item["folder"] for item in items] == ["Производство/Тара"]
        assert items[0]["counted_count"] == 0
        assert items[0]["share"] == 0
        assert items[0]["days_ago"] is None

    def test_share_is_counted_against_the_whole_folder(self, make_product, make_inventory, count_position):
        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, make_product("Первый", folder="Тара"))
        make_product("Второй", folder="Тара")
        make_product("Третий", folder="Тара")
        make_product("Четвёртый", folder="Тара")

        item = blocks.coverage(rows_of())["items"][0]

        assert item["counted_count"] == 1
        assert item["products_count"] == 4
        assert item["share"] == Decimal("0.25")

    def test_days_ago_is_a_median(self, make_product, make_inventory, count_position):
        """Медиана, а не среднее: одна давняя позиция сдвинула бы среднее
        на месяц и назвала бы забытой папку, которую считают регулярно."""
        old = make_inventory(moscow(2026, 5, 27))
        fresh = make_inventory(moscow(2026, 8, 6))
        count_position(old, make_product("Давняя", folder="Тара"))
        count_position(fresh, make_product("Свежая", folder="Тара"))
        count_position(fresh, make_product("Тоже свежая", folder="Тара"))

        item = blocks.coverage(rows_of())["items"][0]
        fresh_days = next(row["days_ago"] for row in rows_of() if row["name"] == "Свежая")

        assert item["days_ago"] == fresh_days

    def test_oldest_folder_is_named(self, make_product, make_inventory, count_position):
        count_position(make_inventory(moscow(2026, 5, 27)),
                       make_product("Этикетка", folder="Производство/Этикетки"))
        count_position(make_inventory(moscow(2026, 8, 6)),
                       make_product("Короб", folder="Хоз. товары/Упаковка"))

        coverage = blocks.coverage(rows_of())

        assert coverage["oldest_folder"] == "Производство/Этикетки"


class TestWorst:
    def test_block_counts_the_same_money_as_the_table(self, make_product, make_inventory, count_position):
        """Блок и таблица — про одно множество: последний пересчёт позиции.

        Сложи блок всю историю, два числа на одном экране означали бы
        разное, оставаясь оба верными, — дефект, который на «Каналах»
        стоил 281 126 ₽ непонимания.
        """
        product = make_product("Короб", cost="10000.000000")
        count_position(make_inventory(moscow(2026, 5, 27)), product,
                       calculated="10.000", counted="0.000")
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="5.000", counted="4.000")

        rows = rows_of()

        assert blocks.worst(rows)["money_kopecks"] == service.totals(rows)["money_kopecks"]
        assert blocks.worst(rows)["money_kopecks"] == -10000

    def test_items_are_sorted_by_size(self, make_product, make_inventory, count_position):
        inventory = make_inventory(moscow(2026, 8, 6))
        count_position(inventory, make_product("Мелочь", cost="100.000000"),
                       calculated="2.000", counted="1.000")
        count_position(inventory, make_product("Плёнка", cost="57626.000000"),
                       calculated="4.000", counted="2.000")

        items = blocks.worst(rows_of())["items"]

        assert [item["name"] for item in items] == ["Плёнка", "Мелочь"]

    def test_unpriced_divergence_is_named(self, make_product, make_inventory, count_position):
        count_position(make_inventory(moscow(2026, 8, 6)),
                       make_product("Тубус", cost=None))

        worst = blocks.worst(rows_of())

        assert worst["unpriced_count"] == 1
        assert worst["items"] == []


class TestRepeats:
    def test_only_repeated_divergence_counts(self, make_product, make_inventory, count_position):
        """Один раз — случайность счёта, дважды — место, где учёт расходится
        с полкой систематически."""
        once = make_product("Разошёлся раз")
        twice = make_product("Расходится всегда")
        first = make_inventory(moscow(2026, 5, 27))
        second = make_inventory(moscow(2026, 8, 6))
        count_position(first, once)
        count_position(first, twice)
        count_position(second, twice)
        count_position(second, once, calculated="5.000", counted="5.000", correction="0")

        repeats = blocks.repeats(rows_of())

        assert repeats["count"] == 1
        assert repeats["items"][0]["name"] == "Расходится всегда"
        assert repeats["items"][0]["diverged_times"] == 2


class TestDocuments:
    def test_store_is_shown_for_every_document(self, make_inventory, make_product, count_position):
        """Складов три, пересчёт трогает один: без склада «считали 06.08»
        читается как «посчитали весь товар»."""
        inventory = make_inventory(moscow(2026, 8, 6), store="Хоз товары")
        count_position(inventory, make_product("Короб"))

        item = blocks.documents(selection.Filters())["items"][0]

        assert item["store_name"] == "Хоз товары"
        assert item["positions_count"] == 1
        assert item["diverged_count"] == 1

    def test_store_filter_narrows_documents(self, make_inventory):
        make_inventory(moscow(2026, 8, 6), store="Хоз товары")
        make_inventory(moscow(2026, 5, 27), store="Производство")

        documents = blocks.documents(selection.Filters(store="Производство"))

        assert documents["count"] == 1
        assert documents["items"][0]["store_name"] == "Производство"

    def test_deleted_document_is_out(self, make_inventory):
        from django.utils import timezone

        inventory = make_inventory(moscow(2026, 8, 6))
        inventory.deleted_at = timezone.now()
        inventory.save(update_fields=["deleted_at"])

        assert blocks.documents(selection.Filters())["count"] == 0


class TestGroupDates:
    """Когда группу и склад считали в последний раз.

    «Когда считали сырьё» — вопрос к группе целиком, и медиана по её
    позициям на него не отвечает: она говорит «типично», а спрашивают
    «когда вообще доходили руки».
    """

    def test_folder_carries_its_last_recount(self, make_product, make_inventory, count_position):
        old = make_inventory(moscow(2026, 5, 27))
        fresh = make_inventory(moscow(2026, 8, 6))
        count_position(old, make_product("Давняя", folder="Тара"))
        count_position(fresh, make_product("Свежая", folder="Тара"))
        make_product("Не считали", folder="Тара")

        item = blocks.coverage(rows_of())["items"][0]

        assert item["last_moment"] == fresh.moment
        assert item["last_days_ago"] < item["days_ago"]

    def test_untouched_folder_has_no_date(self, make_product):
        make_product("Банка", folder="Производство/Тара")

        item = blocks.coverage(rows_of())["items"][0]

        assert item["last_moment"] is None
        assert item["last_days_ago"] is None

    def test_store_recount_takes_the_latest_document(self, make_inventory):
        make_inventory(moscow(2026, 5, 27), store="Производство", number="00001")
        make_inventory(moscow(2026, 6, 3), store="Производство", number="00003")
        make_inventory(moscow(2026, 8, 6), store="Хоз товары", number="00006")

        recounts = blocks.store_recounts(selection.Filters())

        assert [item["store_name"] for item in recounts] == ["Производство", "Хоз товары"]
        assert recounts[0]["number"] == "00003"

    def test_store_without_a_recount_is_absent(self, make_inventory):
        """Склад, который не считали, в сводку не попадает: строка «—» рядом
        с датами читалась бы как сбой, а не как ответ. Что не пересчитано
        вовсе — говорит блок «Что не считали»."""
        make_inventory(moscow(2026, 8, 6), store="Хоз товары")

        assert [item["store_name"] for item in blocks.store_recounts(selection.Filters())] == [
            "Хоз товары"
        ]


class TestStoreCoverage:
    """Доля пересчёта склада: знаменатель — что на складе лежит сейчас.

    Считай мы от всей номенклатуры, «Готовая продукция» выглядела бы
    заброшенной просто потому, что сырьё лежит не на ней.
    """

    def test_share_counts_only_what_lies_here(self, make_product, make_inventory, count_position):
        from decimal import Decimal

        from core.models import StoreStock

        here = make_product("Короб", cost="10000.000000")
        elsewhere = make_product("Отдушка", cost="50000.000000")
        StoreStock.objects.create(product=here, store_name="Хоз товары", quantity=Decimal("5.000"))
        StoreStock.objects.create(product=elsewhere, store_name="Производство", quantity=Decimal("2.000"))
        count_position(make_inventory(moscow(2026, 8, 6), store="Хоз товары"), here)

        by_store = {item["store_name"]: item for item in blocks.store_recounts(selection.Filters())}

        assert by_store["Хоз товары"]["products_count"] == 1
        assert by_store["Хоз товары"]["counted_count"] == 1
        assert by_store["Хоз товары"]["share"] == 1
        assert by_store["Производство"]["counted_count"] == 0

    def test_recount_on_another_store_does_not_count(self, make_product, make_inventory, count_position):
        """Пересчёт на соседнем складе про этот ничего не говорит."""
        from decimal import Decimal

        from core.models import StoreStock

        product = make_product("Короб", cost="10000.000000")
        StoreStock.objects.create(product=product, store_name="Производство", quantity=Decimal("5.000"))
        count_position(make_inventory(moscow(2026, 8, 6), store="Хоз товары"), product)

        by_store = {item["store_name"]: item for item in blocks.store_recounts(selection.Filters())}

        assert by_store["Производство"]["counted_count"] == 0

    def test_unchecked_money_is_what_was_not_counted(self, make_product, make_inventory, count_position):
        """Деньги превращают долю из отметки в задачу: «18 %» само по себе
        не говорит, стоит ли идти считать."""
        from decimal import Decimal

        from core.models import StoreStock

        counted = make_product("Короб", cost="10000.000000")
        missed = make_product("Отдушка", cost="50000.000000")
        StoreStock.objects.create(product=counted, store_name="Производство", quantity=Decimal("5.000"))
        StoreStock.objects.create(product=missed, store_name="Производство", quantity=Decimal("2.000"))
        count_position(make_inventory(moscow(2026, 8, 6), store="Производство"), counted)

        item = blocks.store_recounts(selection.Filters())[0]

        assert item["unchecked_kopecks"] == 100000

    def test_store_without_stock_still_shows_its_recount(self, make_product, make_inventory, count_position):
        """Склад, с которого всё увезли, из сводки не исчезает: дата пересчёта
        по нему остаётся фактом, а доля считать нечего."""
        count_position(make_inventory(moscow(2026, 8, 6), store="Хоз товары"), make_product("Короб"))

        item = blocks.store_recounts(selection.Filters())[0]

        assert item["store_name"] == "Хоз товары"
        assert item["products_count"] == 0
        assert item["share"] is None


class TestNumbersAgree:
    """Числа с одной подписью обязаны означать одно.

    «Разошлось» стоит и в подвале таблицы, и в заголовке блока «Где
    не сходится». Считай подвал всю историю, а блок — последний пересчёт,
    позиция, разошедшаяся в июне и сошедшаяся в августе, попадала бы
    в первое число и не попадала во второе, — и оба остались бы формально
    верными.
    """

    def test_diverged_count_is_the_same_everywhere(
        self, make_product, make_inventory, count_position
    ):
        from api.inventory.services import inventory as service

        product = make_product("Короб", cost="10000.000000")
        count_position(make_inventory(moscow(2026, 5, 27)), product,
                       calculated="10.000", counted="8.000")
        count_position(make_inventory(moscow(2026, 8, 6)), product,
                       calculated="8.000", counted="8.000", correction="0")

        rows = rows_of()

        assert service.totals(rows)["diverged_count"] == blocks.worst(rows)["diverged_count"] == 0
        # История при этом не потеряна — её показывает своя графа.
        assert rows[0]["diverged_times"] == 1


class TestStoreless:
    """Документ без склада виден, а не пропадает молча.

    Пустое имя означает, что `expand=store` не доехал, — и синк об этом
    предупреждает. Выпади такой документ из сводки складов, он остался бы
    в счётчике заголовка: «6 инвентаризаций», из которых видно пять.
    """

    def test_document_without_store_gets_its_own_row(self, make_inventory, make_product, count_position):
        count_position(make_inventory(moscow(2026, 8, 6), store=""), make_product("Короб"))

        items = blocks.store_recounts(selection.Filters())

        assert [item["store_name"] for item in items] == [blocks.NO_STORE]
        assert items[0]["moment"] is not None

    def test_paper_and_store_row_share_one_label(self, make_inventory, make_product, count_position):
        """Подпись одна на оба списка.

        Страница группирует документы по имени склада: пустое имя против
        «Склад не указан» развело бы их по разным карточкам, и документ
        снова стал бы невидим — теперь уже на фронте.
        """
        count_position(make_inventory(moscow(2026, 8, 6), store=""), make_product("Короб"))

        store = blocks.store_recounts(selection.Filters())[0]
        paper = blocks.documents(selection.Filters())["items"][0]

        assert store["store_name"] == paper["store_name"] == blocks.NO_STORE
