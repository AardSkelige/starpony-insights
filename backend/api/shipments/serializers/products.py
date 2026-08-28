"""Контракт страницы «Товары в отгрузках»."""

from rest_framework import serializers

from api.shipments.serializers.common import (
    SalesChannelSerializer,
    SelectionQuerySerializer,
    StockSerializer,
)
from api.shipments.services.products import DEFAULT_ORDERING, ORDERING


class ShipmentProductsQuerySerializer(SelectionQuerySerializer):
    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


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


class ShipmentProductDetailSerializer(serializers.Serializer):
    channels = ChannelShareSerializer(many=True)
    documents = ProductDocumentSerializer(many=True)
    # Остаток известен не по всем товарам: в отчёте МойСклада его может
    # не быть вовсе. `null` честнее нуля, который читается как «кончился».
    stock = StockSerializer(allow_null=True)


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
