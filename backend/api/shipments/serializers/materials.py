"""Контракт страницы «Материалы в отгрузках».

Ключевое отличие от соседней страницы — объяснение. Число в колонке
«Израсходовано» посчитано разворачиванием техкарт, и панель раскрывает его
до слагаемых: изделие → путь по техкартам → сколько пришло этим путём.
Поэтому у деталей три уровня вложенности, а не два.
"""

from rest_framework import serializers

from api.common.serializers import (
    MaterialCoverageSerializer,
    FilterOptionSerializer,
    MaterialHeadSerializer,
    StockSerializer,
)
from api.shipments.serializers.common import ShipmentQuerySerializer
from api.shipments.services.materials import DEFAULT_ORDERING, ORDERING


class ShipmentMaterialsQuerySerializer(ShipmentQuerySerializer):
    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


class ShipmentMaterialRowSerializer(serializers.Serializer):
    material_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)

    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    products_count = serializers.IntegerField()

    # Цена приходит рядом со стоимостью — вместе с датой закупки, из которой
    # взята. Так формула собирается из полученного, а не пересчитывается.
    # `null` там, где материал ни разу не покупали: ноль читался бы
    # как «достался даром».
    price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    price_moment = serializers.DateTimeField(allow_null=True)
    cost_kopecks = serializers.IntegerField(allow_null=True)
    cost_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class WithoutPlanRowSerializer(serializers.Serializer):
    """Проданное, чего техкарта не описывает: услуги и покупные товары.

    Отдельным списком, а не строкой в таблице: доставка не сырьё, и в сумму
    материалов она не входит. Спрятать её тоже нельзя — тогда «сырья на
    399 686 ₽» читалось бы как расход по всей выручке.
    """

    product_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)
    is_service = serializers.BooleanField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    revenue_kopecks = serializers.IntegerField()


class ShipmentMaterialsTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска.

    Обязан сходиться со сложением колонки: файл и экран открывают затем,
    чтобы складывать, и расхождение заметят раньше нас.
    """

    materials_count = serializers.IntegerField()
    cost_kopecks = serializers.IntegerField()
    # Сколько показанное занимает в стоимости всей выборки. Без поиска —
    # сто процентов; с поиском — доля найденного, и она сходится
    # со сложением колонки.
    cost_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    priced_count = serializers.IntegerField()
    unpriced_count = serializers.IntegerField()


class ShipmentMaterialsCoverageSerializer(serializers.Serializer):
    """Насколько полное число видит человек — про выборку отгрузок целиком.

    Поиск сюда не входит намеренно: он сужает список материалов, а не то,
    что отгрузили. Возьми стоимость с учётом поиска, а выручку без —
    получится дробь, которая выглядит обычным процентом и врёт молча.
    """

    materials_count = serializers.IntegerField()
    cost_kopecks = serializers.IntegerField()
    # Охват расчёта: сколько строк сумму получили, а сколько нет. Без этих
    # чисел итог выглядит полным, хотя часть материалов в него не вошла.
    priced_count = serializers.IntegerField()
    unpriced_count = serializers.IntegerField()

    sold_products_count = serializers.IntegerField()
    exploded_products_count = serializers.IntegerField()
    without_plan_count = serializers.IntegerField()

    revenue_kopecks = serializers.IntegerField()
    documents_count = serializers.IntegerField()
    # Больше единицы — не ошибка, а факт: 6 июля 2026 выручка 7,13 ₽ против
    # сырья на 290,91 ₽, потому что товар отгрузили за 0 ₽. Разрядность взята
    # с запасом: у поля 9 знаков доля 4080% роняла весь ответ пятисотой.
    cost_share_of_revenue = serializers.DecimalField(
        max_digits=16, decimal_places=8, allow_null=True
    )


class ShipmentMaterialsSerializer(serializers.Serializer):
    synced_at = serializers.DateTimeField(allow_null=True)
    count = serializers.IntegerField()
    totals = ShipmentMaterialsTotalsSerializer()
    coverage = ShipmentMaterialsCoverageSerializer()
    results = ShipmentMaterialRowSerializer(many=True)
    without_plan = WithoutPlanRowSerializer(many=True)
    channels = FilterOptionSerializer(many=True)


class MaterialPathSerializer(serializers.Serializer):
    """Один путь по техкартам и то, сколько материала пришло именно им.

    Количество обязательно: без него путь говорит «через замес и через
    розлив», но не отвечает, чего сколько, — а объяснение, которое не
    складывается обратно в объясняемое число, объяснением не является.
    """

    chain = serializers.ListField(child=serializers.CharField())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class MaterialSourceSerializer(serializers.Serializer):
    """Изделие, из-за продажи которого материал израсходован."""

    product_id = serializers.IntegerField()
    name = serializers.CharField()
    sold_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    sold_uom = serializers.CharField(allow_blank=True)
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    paths = MaterialPathSerializer(many=True)


class MaterialPriceSerializer(serializers.Serializer):
    """Откуда взялась цена: документ, дата, поставщик.

    Число, посчитанное по цене, обязано назвать её источник. Иначе колонка
    «Стоимость» остаётся суммой, за которую никто не отвечает.
    """

    price_kopecks = serializers.DecimalField(max_digits=18, decimal_places=6)
    moment = serializers.DateTimeField()
    document_number = serializers.CharField()
    supplier = serializers.CharField()


class MaterialRestSerializer(serializers.Serializer):
    """Свёрнутый хвост списка источников.

    Без него показанные слагаемые не складывались бы в число, которое панель
    объясняет: у воды пятьдесят девять изделий-источников, а видно двадцать.
    """

    products_count = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class MaterialRateSerializer(serializers.Serializer):
    """Норма расхода: сколько материала уходит на одно изделие.

    Группой, а не по изделию: у 121 материала из 161 норма одна на все,
    и шестнадцать одинаковых строк не сообщают ничего сверх одной. У 40
    норма различается — у диметикона 200 г против 20 г, разница в десять
    раз, и увидеть её больше негде.
    """

    rate = serializers.DecimalField(max_digits=18, decimal_places=6)
    products_count = serializers.IntegerField()
    # Три крупнейших изделия этой нормы — примеры, а не весь список.
    examples = serializers.ListField(child=serializers.CharField())


class MaterialShareSerializer(serializers.Serializer):
    """Изделие и его доля в расходе материала."""

    product_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class MaterialShareRestSerializer(serializers.Serializer):
    """Свёрнутый хвост распределения.

    Без него показанные доли не складываются в сто процентов, а количества —
    в объясняемое число, и расхождение спишут на расчёт.
    """

    products_count = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class MaterialDistributionSerializer(serializers.Serializer):
    top = MaterialShareSerializer(many=True)
    rest = MaterialShareRestSerializer(allow_null=True)


class ShipmentMaterialDetailSerializer(serializers.Serializer):
    material = MaterialHeadSerializer()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    cost_kopecks = serializers.IntegerField(allow_null=True)
    price = MaterialPriceSerializer(allow_null=True)
    # Остаток известен не по всем материалам. `null` честнее нуля,
    # который читается как «кончился».
    stock = StockSerializer(allow_null=True)
    coverage = MaterialCoverageSerializer()
    rates = MaterialRateSerializer(many=True)
    distribution = MaterialDistributionSerializer()
    # Сколько изделий-источников всего и первые из них. Число рядом со
    # списком: у воды источников пятьдесят девять, показаны двадцать.
    sources_count = serializers.IntegerField()
    # Сколько из них получают материал несколькими путями — по всем
    # источникам, а не по показанным. Заголовок свёрнутого разбора говорит
    # этим числом, стоит ли его открывать.
    multi_path_count = serializers.IntegerField()
    sources = MaterialSourceSerializer(many=True)
    # `null`, когда показаны все источники: пустой хвост и свёрнутый хвост —
    # разные вещи, и в интерфейсе они выглядят по-разному.
    rest = MaterialRestSerializer(allow_null=True)
