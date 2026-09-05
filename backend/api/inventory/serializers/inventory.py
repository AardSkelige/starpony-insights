"""Контракт страницы «Инвентаризация».

Два числа здесь расчётные, и оба уходят вместе со своими составляющими:
«в деньгах» — это расхождение, умноженное на себестоимость из остатков,
а не сумма из документа. В учёте цена заполнена у 10 позиций из 55, поэтому
`correctionSum` там нулевой при живой недостаче — показать его значило бы
повторить молчание учёта (`CLAUDE.md` §4).

`null` вместо нуля везде, где величины **не существует**: позицию не считали
ни разу, себестоимости нет, папку не открывали. Ноль читался бы как
«сошлось» ровно там, где ответа нет вовсе.
"""

from rest_framework import serializers

from api.common.serializers import FilterOptionSerializer, SelectionQuerySerializer
from api.inventory.services.inventory import DEFAULT_ORDERING, ORDERING


class InventoryQuerySerializer(SelectionQuerySerializer):
    """Выборка: поиск, склад, папка, порядок.

    Периода нет: «что давно не считали» — состояние на сегодня, и период
    не сузил бы выборку, а спрятал бы позиции, не попавшие ни в один
    пересчёт, — то есть ровно те, ради которых страницу открывают.
    Поля периода унаследованы от общего сериализатора и не используются.
    """

    store = serializers.CharField(required=False, allow_blank=True, default="")
    folder = serializers.CharField(required=False, allow_blank=True, default="")
    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


class InventoryRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField()
    folder = serializers.CharField()
    # Рядом с количеством обязательна: «5 730» у спирта — граммы,
    # у короба — штуки, и без неё это одно и то же число.
    uom = serializers.CharField()

    counted_times = serializers.IntegerField()
    diverged_times = serializers.IntegerField()

    # Последний пересчёт позиции. Последний, а не суммарный: «числилось 42,
    # нашли 5» — факт одного дня, и складывать такие пары по разным
    # пересчётам значило бы показать число, которого не было ни в одном
    # документе.
    last_moment = serializers.DateTimeField(allow_null=True)
    last_store = serializers.CharField()
    days_ago = serializers.IntegerField(allow_null=True)
    calculated = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    counted = serializers.DecimalField(max_digits=18, decimal_places=3, allow_null=True)
    correction = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )

    # Расчётное число и то, чем его считали: без себестоимости рядом формулу
    # на экране показать нечем.
    correction_money_kopecks = serializers.IntegerField(allow_null=True)
    cost_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    # Сколько числится сейчас: пересчитывать позицию, которой на складе нет,
    # незачем — а по одному расхождению трёхмесячной давности это не видно.
    stock_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )


class InventoryTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска."""

    products_count = serializers.IntegerField()
    never_counted_count = serializers.IntegerField()
    diverged_count = serializers.IntegerField()
    money_kopecks = serializers.IntegerField()
    # Строки, где расхождение есть, а оценить его нечем. Без этого числа
    # итог выглядел бы полным.
    unpriced_count = serializers.IntegerField()


class CoverageFolderSerializer(serializers.Serializer):
    folder = serializers.CharField()
    products_count = serializers.IntegerField()
    counted_count = serializers.IntegerField()
    share = serializers.DecimalField(max_digits=9, decimal_places=8, allow_null=True)
    # Медиана, а не среднее: одна давняя позиция в папке из сорока сдвинула бы
    # среднее на месяц и назвала бы папку забытой.
    days_ago = serializers.IntegerField(allow_null=True)
    # Когда до этой группы вообще доходили руки. Это другой ответ, чем
    # медиана: «когда считали сырьё» спрашивают чаще, чем «типично по его
    # позициям».
    last_moment = serializers.DateTimeField(allow_null=True)
    last_days_ago = serializers.IntegerField(allow_null=True)


class CoverageSerializer(serializers.Serializer):
    """Блок «Что не считали»: доля пересчитанного по папкам."""

    products_count = serializers.IntegerField()
    counted_count = serializers.IntegerField()
    never_counted_count = serializers.IntegerField()
    oldest_folder = serializers.CharField()
    oldest_days_ago = serializers.IntegerField(allow_null=True)
    items = CoverageFolderSerializer(many=True)


class WorstItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    correction = serializers.DecimalField(max_digits=18, decimal_places=3)
    uom = serializers.CharField()
    money_kopecks = serializers.IntegerField()


class WorstSerializer(serializers.Serializer):
    """Блок «Где не сходится»: по последнему пересчёту каждой позиции.

    По последнему, а не по всей истории, — как и таблица. Иначе два числа
    на одном экране означали бы разное, оставаясь оба верными.
    """

    money_kopecks = serializers.IntegerField()
    diverged_count = serializers.IntegerField()
    counted_count = serializers.IntegerField()
    unpriced_count = serializers.IntegerField()
    items = WorstItemSerializer(many=True)


class RepeatItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    folder = serializers.CharField()
    counted_times = serializers.IntegerField()
    diverged_times = serializers.IntegerField()


class RepeatsSerializer(serializers.Serializer):
    """Блок «Расходится из раза в раз» — единственный про всю историю."""

    count = serializers.IntegerField()
    items = RepeatItemSerializer(many=True)


class InventoryDocumentSerializer(serializers.Serializer):
    inventory_id = serializers.IntegerField()
    number = serializers.CharField()
    moment = serializers.DateTimeField()
    # Складов три, и пересчёт всегда трогает один: без склада «считали 06.08»
    # читается как «посчитали весь товар».
    store_name = serializers.CharField()
    positions_count = serializers.IntegerField()
    diverged_count = serializers.IntegerField()
    description = serializers.CharField()


class StoreRecountSerializer(serializers.Serializer):
    """Склад: когда считали и сколько его пересчитано.

    Пересчёт — операция склада, а не папки: документ всегда про один склад
    целиком. Знаменатель — позиции, которые на складе **лежат** сейчас:
    доля от всей номенклатуры объявила бы «Готовую продукцию» заброшенной
    за то, что на ней нет сырья.
    """

    store_name = serializers.CharField()
    number = serializers.CharField()
    moment = serializers.DateTimeField(allow_null=True)
    days_ago = serializers.IntegerField(allow_null=True)

    products_count = serializers.IntegerField()
    counted_count = serializers.IntegerField()
    share = serializers.DecimalField(max_digits=9, decimal_places=8, allow_null=True)
    # Во сколько обходится непроверенное. Ровно это число превращает
    # «пересчитано 18 %» из отметки в задачу.
    unchecked_kopecks = serializers.IntegerField()


class InventoryDocumentsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    stores = StoreRecountSerializer(many=True)
    items = InventoryDocumentSerializer(many=True)


class InventorySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    synced_at = serializers.DateTimeField(allow_null=True)
    totals = InventoryTotalsSerializer()
    coverage = CoverageSerializer()
    worst = WorstSerializer()
    repeats = RepeatsSerializer()
    documents = InventoryDocumentsSerializer()
    stores = FilterOptionSerializer(many=True)
    folders = serializers.ListField(child=serializers.CharField())
    results = InventoryRowSerializer(many=True)
