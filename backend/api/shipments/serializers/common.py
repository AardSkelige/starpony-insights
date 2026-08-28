"""Общее для контрактов раздела: фильтры выборки и справочник каналов.

Сериализаторы ответов нужны не для валидации, а для схемы: из неё
генерируются типы фронтенда, и без них расхождение фронта с бэком
перестаёт ловиться на сборке.

Деньги уходят целыми копейками, удельные величины — строкой Decimal.
Рубли и проценты появляются только на экране: перевести их здесь значило бы
потерять знаки ровно там, где они значат разницу между «сошлось с учётом»
и «почти сошлось».
"""

from rest_framework import serializers

from api.shipments.services.selection import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class SelectionQuerySerializer(serializers.Serializer):
    """Фильтры страницы раздела. Они же живут в адресной строке — ссылку
    можно переслать, и она откроется тем же, что человек видел.

    Общая часть у обеих страниц: период, канал, поиск и разбиение на страницы
    устроены одинаково. Разное — только допустимые сортировки, они задаются
    наследником: у «Товаров» есть `-revenue`, у «Материалов» такого ключа нет.
    """

    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    channel_id = serializers.IntegerField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    # Высота страницы одна на раздел, и слишком большая отклоняется, а не
    # обрезается молча: ответ на `?page_size=1000` должен сказать, что столько
    # не отдаём, — иначе человек решит, что строк действительно 200.
    page_size = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_PAGE_SIZE, default=DEFAULT_PAGE_SIZE
    )

    def validate(self, attrs):
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_from": "Начало периода позже его конца."}
            )
        return attrs


class SalesChannelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class StockSerializer(serializers.Serializer):
    """Что лежит на складе сейчас — одинаково для товара и для материала.

    Один сериализатор, а не два одинаковых: из схемы генерируются типы
    фронтенда, и два близнеца дают два типа, под которые пишутся два
    компонента. Так и вышло — блок «Склад» разошёлся между страницами
    и на одной из них перестал отличать сбой связи от «остатка нет».
    """

    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    reserved = serializers.DecimalField(max_digits=18, decimal_places=3)
    available = serializers.DecimalField(max_digits=18, decimal_places=3)
    stock_days = serializers.IntegerField(allow_null=True)


