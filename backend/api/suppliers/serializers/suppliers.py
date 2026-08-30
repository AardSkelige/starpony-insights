"""Контракт страницы «Поставщики».

Отличие от соседних страниц — в двух числах, которых больше нигде нет:
регулярность и срок поставки. Оба медианы, и оба приходят вместе с разбросом
и средним, из которых получены: у «Ревады-Невы» две поставки, 2 и 40 дней,
и медиана 21 без разброса рядом описывает срок, которого не было ни разу.

`null` вместо нуля везде, где величина неизвестна: у семи поставщиков
из двадцати трёх поставка была одна, и промежутка между поставками
не существует. Ноль читался бы как «возит каждый день».

**А вот у срока поставки ноль — это ответ.** У «Интернет Решений»,
«Принтеца» и «ИП Белых» медиана ровно 0: у них забирают, а не ждут доставку.
Подменить это прочерком значило бы соврать про половину закупок.
"""

from rest_framework import serializers

from api.common.serializers import SelectionQuerySerializer
from api.suppliers.services.suppliers import DEFAULT_ORDERING, ORDERING


class SuppliersQuerySerializer(SelectionQuerySerializer):
    """Выборка страницы: период, поиск, страница, порядок.

    Справочника для сужения здесь нет намеренно. У отгрузок это канал продаж,
    у «Материалов в приёмках» — поставщик; здесь поставщик и есть строка,
    и фильтр по нему оставил бы в таблице ровно одну.
    """

    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


class SpanSerializer(serializers.Serializer):
    """Медиана в днях вместе с тем, из чего она получена.

    Один тип на регулярность и на срок поставки: поля у них совпадают
    до буквы, и два близнеца в схеме дали бы фронтенду два типа, под которые
    пишутся два компонента. Так уже расходился блок «Склад».

    Названия полей нейтральны к смыслу (`days`, а не `interval_days`)
    именно поэтому: подпись даёт колонка, а не контракт.
    """

    # Медиана, а не среднее. На боевых данных среднее по срокам 4,77 дня
    # против медианы 1,00 — впятеро: половина закупок оформляется одним днём,
    # вторая идёт до сорока, и среднее описывает несуществующую середину.
    days = serializers.DecimalField(
        max_digits=8, decimal_places=1, allow_null=True
    )
    # Знаменатель медианы: сколько промежутков или пар удалось измерить.
    # Приходит рядом с ответом, чтобы формула собиралась из полученного.
    measurements = serializers.IntegerField()
    min_days = serializers.IntegerField(allow_null=True)
    max_days = serializers.IntegerField(allow_null=True)
    # Среднее — только в объяснении, рядом с медианой. Расхождение между ними
    # само говорит, насколько поставки рваные: у «Полицвета» 22,5 против 6,5.
    average_days = serializers.DecimalField(
        max_digits=8, decimal_places=1, allow_null=True
    )


class RegularitySerializer(SpanSerializer):
    measurements = serializers.IntegerField(source="gaps")


class LeadTimeSerializer(SpanSerializer):
    measurements = serializers.IntegerField(source="pairs")
    # Приёмки, у которых заказа в зеркале нет. Показывается словами:
    # «срок по 12 приёмкам из 14» честнее, чем молчаливая медиана по части.
    unlinked = serializers.IntegerField()


class SupplierMaterialSerializer(serializers.Serializer):
    name = serializers.CharField()
    amount_kopecks = serializers.IntegerField()
    share = serializers.DecimalField(max_digits=9, decimal_places=8, allow_null=True)


class SupplierMaterialsSerializer(serializers.Serializer):
    """Что именно берём у поставщика: крупнейшие плюс свёрнутый хвост.

    По суммам, а не по количествам: у материалов разные единицы — граммы
    против штук, — и сложить их нельзя. Деньги единственное, что у них общее.
    """

    items = SupplierMaterialSerializer(many=True)
    rest_count = serializers.IntegerField()
    rest_amount_kopecks = serializers.IntegerField()


class SupplierRowSerializer(serializers.Serializer):
    supplier_id = serializers.IntegerField()
    name = serializers.CharField()

    supplies_count = serializers.IntegerField()
    # Дней поставок, а не документов: три приёмки одним днём — одна поставка,
    # разбитая на бумаги. Знаменатель регулярности именно этот.
    delivery_days = serializers.IntegerField()
    amount_kopecks = serializers.IntegerField()
    amount_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )

    first_moment = serializers.DateTimeField()
    last_moment = serializers.DateTimeField()

    materials_count = serializers.IntegerField()
    positions_count = serializers.IntegerField()
    # Сколько строк пришло даром: у «Принтеца» 97 из 129 — образцы, бонусы
    # и допечатка. Без этого числа его суммы объяснить нечем.
    free_positions_count = serializers.IntegerField()

    regularity = RegularitySerializer()
    lead_time = LeadTimeSerializer()
    # Что у него берём. Числа «39 наименований» без ответа «каких» страница
    # показывала, а узнать это можно было только на соседней странице.
    materials = SupplierMaterialsSerializer()


class SuppliersTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска."""

    suppliers_count = serializers.IntegerField()
    supplies_count = serializers.IntegerField()
    amount_kopecks = serializers.IntegerField()
    amount_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    # Через объединение, а не сложением колонки: 21 материал приходит больше
    # чем от одного поставщика и был бы посчитан дважды.
    materials_count = serializers.IntegerField()


class SuppliersCoverageSerializer(serializers.Serializer):
    """Сводка — про выборку приёмок целиком. Поиск её не трогает."""

    suppliers_count = serializers.IntegerField()
    supplies_count = serializers.IntegerField()
    amount_kopecks = serializers.IntegerField()
    positions_count = serializers.IntegerField()
    materials_count = serializers.IntegerField()
    free_positions_count = serializers.IntegerField()
    # Объясняют прочерки в колонках: у семи поставщиков из двадцати трёх
    # поставка была одна, и промежутка между поставками не существует.
    with_regularity_count = serializers.IntegerField()
    with_lead_time_count = serializers.IntegerField()
    # Приёмки без заказа в зеркале. На боевых данных ноль, и появление
    # первой обязано быть видно: срок посчитается не по всей истории.
    unlinked_supplies_count = serializers.IntegerField()


class SuppliersSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    synced_at = serializers.DateTimeField(allow_null=True)
    totals = SuppliersTotalsSerializer()
    coverage = SuppliersCoverageSerializer()
    results = SupplierRowSerializer(many=True)
