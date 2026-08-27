"""Контракт страницы «Товары в отгрузках».

Сериализаторы ответов нужны не для валидации, а для схемы: из неё
генерируются типы фронтенда, и без них расхождение фронта с бэком
перестаёт ловиться на сборке.

Деньги уходят целыми копейками, удельные величины — строкой Decimal.
Рубли и проценты появляются только на экране: перевести их здесь значило бы
потерять знаки ровно там, где они значат разницу между «сошлось с учётом»
и «почти сошлось».
"""

from rest_framework import serializers

from api.shipments.services.products import (
    DEFAULT_ORDERING,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ORDERING,
)


class ShipmentProductsQuerySerializer(serializers.Serializer):
    """Фильтры страницы. Они же живут в адресной строке — ссылку можно переслать."""

    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    channel_id = serializers.IntegerField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
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


class ShipmentProductRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)

    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()
    documents_count = serializers.IntegerField()

    # Расчётные. Приходят вместе с составляющими — выручкой и количеством, —
    # так что формулу фронт собирает из полученного, а не пересчитывает сам.
    avg_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    avg_price_paid_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    revenue_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class ShipmentProductsTotalsSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()
    documents_count = serializers.IntegerField()
    products_count = serializers.IntegerField()


class SalesChannelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ChannelShareSerializer(serializers.Serializer):
    """Доля канала в продажах товара. Основа полос в раскрытии строки."""

    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()


class ProductDocumentSerializer(serializers.Serializer):
    number = serializers.CharField()
    moment = serializers.DateTimeField()
    agent = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    total_kopecks = serializers.IntegerField()


class ProductStockSerializer(serializers.Serializer):
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    reserved = serializers.DecimalField(max_digits=18, decimal_places=3)
    available = serializers.DecimalField(max_digits=18, decimal_places=3)
    stock_days = serializers.IntegerField(allow_null=True)


class ShipmentProductDetailSerializer(serializers.Serializer):
    channels = ChannelShareSerializer(many=True)
    documents = ProductDocumentSerializer(many=True)
    # Остаток известен не по всем товарам: в отчёте МойСклада его может
    # не быть вовсе. `null` честнее нуля, который читается как «кончился».
    stock = ProductStockSerializer(allow_null=True)


class ShipmentProductsSerializer(serializers.Serializer):
    # Отметка «данные на 14:32» — часть ответа, а не украшение шапки:
    # без неё человек не отличит свежие числа от вчерашних.
    synced_at = serializers.DateTimeField(allow_null=True)
    count = serializers.IntegerField()
    totals = ShipmentProductsTotalsSerializer()
    results = ShipmentProductRowSerializer(many=True)
    # Наполнение фильтра приходит вместе с данными: своего запроса за девятью
    # значениями фронт не делает, и список не может разойтись с выборкой.
    channels = SalesChannelSerializer(many=True)
