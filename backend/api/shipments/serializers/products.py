"""Контракт страницы «Товары в отгрузках»."""

from rest_framework import serializers

from api.common.serializers import FilterOptionSerializer, StockSerializer
from api.shipments.serializers.common import ShipmentQuerySerializer
from api.shipments.services.products import DEFAULT_ORDERING, ORDERING


class ShipmentProductsQuerySerializer(ShipmentQuerySerializer):
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
    # Сколько показанное занимает в выручке выборки. Без поиска это ровно
    # сто процентов, с поиском — доля найденного, и она сходится
    # со сложением колонки. Жёсткое «100 %» стояло бы над колонкой,
    # где доли складываются в четырнадцать.
    revenue_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class ChannelShareSerializer(serializers.Serializer):
    """Доля канала в продажах товара. Основа полос в раскрытии строки."""

    id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()


class AgentShareSerializer(serializers.Serializer):
    """Контрагент с количеством: и покупатель, и получатель бесплатного.

    Один тип на оба блока — поля совпадают до буквы, а два близнеца в схеме
    дали бы фронтенду два типа, под которые пишутся два компонента.
    """

    # Идентификатор, а не имя: `Counterparty.name` не уникален, и два разных
    # контрагента с одинаковым названием обязаны остаться двумя строками.
    agent_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()
    documents_count = serializers.IntegerField()


class RecipientsSerializer(serializers.Serializer):
    """Крупнейшие контрагенты плюс свёрнутый хвост."""

    agents = AgentShareSerializer(many=True)
    rest_agents_count = serializers.IntegerField()
    rest_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)


class TimelinePointSerializer(serializers.Serializer):
    """Один столбик: начало промежутка и что в него попало."""

    start = serializers.DateField()
    # Последний день промежутка. Без него одна дата рядом с «по неделям»
    # читается как день — вопрос «это дни видимо?» возник на первом показе.
    end = serializers.DateField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()


class TimelineSerializer(serializers.Serializer):
    """Продажи во времени. Заменило журнал последних отгрузок.

    Шаг подбирается под период на сервере и приходит подписью: два места,
    решающие это по-своему, разъедутся, а человек обязан видеть, в чём мерят,
    иначе смена шага читается как смена данных.
    """

    step = serializers.CharField()
    step_label = serializers.CharField()
    points = TimelinePointSerializer(many=True)


class ShipmentProductDetailSerializer(serializers.Serializer):
    channels = ChannelShareSerializer(many=True)
    timeline = TimelineSerializer()
    # `null` — платных отгрузок не было: товар только раздавали.
    buyers = RecipientsSerializer(allow_null=True)
    # `null` — бесплатных отгрузок у этого товара не было.
    free = RecipientsSerializer(allow_null=True)
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
    channels = FilterOptionSerializer(many=True)
