"""Контракт страницы «Материалы в приёмках».

Отличие от страниц отгрузок — в том, что здесь три разных числа про цену,
и путать их нельзя: средняя за период, последняя и её изменение к предыдущей
закупке. Каждое приходит со своими составляющими, чтобы фронт собирал
формулу из полученного, а не пересчитывал сам.

`null` вместо нуля везде, где величина неизвестна: у 24 наименований цены
нет вовсе (приходили только даром), у 130 нет предыдущей закупки, с которой
можно сравнить. Ноль читался бы как «достался даром» и «цена не менялась» —
оба утверждения были бы ложью об учёте.
"""

from rest_framework import serializers

from api.common.serializers import (
    MaterialCoverageSerializer,
    FilterOptionSerializer,
    MaterialHeadSerializer,
    SelectionQuerySerializer,
    StockSerializer,
)
from api.supplies.services.materials import DEFAULT_ORDERING, ORDERING


class SupplyQuerySerializer(SelectionQuerySerializer):
    """Выборка приёмок: общее плюс поставщик.

    Канала продаж здесь нет и быть не может: товар приходит от контрагента,
    а не через Озон.
    """

    supplier_id = serializers.IntegerField(required=False, allow_null=True)


class SupplyMaterialsQuerySerializer(SupplyQuerySerializer):
    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


class PricePointSerializer(serializers.Serializer):
    """Точка ряда цен: когда и почём. Дата обязательна вместе с ценой.

    Линия строится по времени, а не по номеру закупки: между 28.02 и 14.05
    два с половиной месяца, между 01.07 и 30.07 — один, и равные промежутки
    на экране соврали бы о том, как быстро материал дорожает.
    """

    moment = serializers.DateTimeField()
    price_kopecks = serializers.DecimalField(max_digits=18, decimal_places=6)


class SupplyMaterialRowSerializer(serializers.Serializer):
    material_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)
    # Материал, пришедший в разных единицах, складывать нельзя: килограмм
    # против грамма ошибается ровно в тысячу раз и на глаз незаметен.
    mixed_uom = serializers.BooleanField()

    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    # Сколько из пришедшего досталось даром — образцы, бонусы, допечатка.
    # На склад оно поступило и из количества не вычитается; в цену не входит.
    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    paid_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    amount_kopecks = serializers.IntegerField()
    amount_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )

    # Сумма ÷ оплаченное количество. Приходит вместе со знаменателем:
    # деление на всё количество занизило бы цену вдвое там, где половина
    # пришла даром.
    avg_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )

    # Последняя закупка с ценой — вместе с тем, чем она себя объясняет.
    last_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    last_moment = serializers.DateTimeField(allow_null=True)
    last_document_number = serializers.CharField(allow_null=True)
    last_supplier = serializers.CharField(allow_null=True)

    # Динамика к предыдущей закупке — обе цены рядом, чтобы формула
    # собиралась из полученного. Разрядность с запасом: лауроилглутамат
    # подорожал на 278%, а поле в девять знаков вмещает только меньше десяти.
    previous_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    # Количества обеих сравниваемых закупок: «5 000 г по 0,45 → 1 000 г
    # по 1,70» объясняет рост на 278 % куда лучше, чем сами цены. Партия
    # впятеро меньше — и это часть ответа, без которой процент выглядит
    # чистым подорожанием.
    previous_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    last_quantity = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    price_change = serializers.DecimalField(
        max_digits=16, decimal_places=8, allow_null=True
    )

    # Ряд цен за период — линией в колонке «Цена». Только закупки с ценой:
    # бесплатная приёмка нарисовала бы падение до нуля и обратно. Пустой
    # список у 24 наименований, один элемент у 130 — линии там нет,
    # и на её месте прочерк, а не прямая.
    prices = PricePointSerializer(many=True)

    supplies_count = serializers.IntegerField()
    suppliers_count = serializers.IntegerField()


class SupplyMaterialsTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска.

    Обязан сходиться со сложением колонки: файл и экран открывают затем,
    чтобы складывать, и расхождение заметят раньше нас.
    """

    materials_count = serializers.IntegerField()
    amount_kopecks = serializers.IntegerField()
    amount_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    priced_count = serializers.IntegerField()
    unpriced_count = serializers.IntegerField()
    # Приёмки и поставщики показанных строк. Отдельно от `coverage`: там те же
    # числа по всей выборке, и подписать ими подвал значило бы получить
    # «8 материалов из 93 приёмок», где 93 описывают все 212.
    documents_count = serializers.IntegerField()
    suppliers_count = serializers.IntegerField()


class SupplyMaterialsCoverageSerializer(serializers.Serializer):
    """Насколько полное число видит человек — про выборку приёмок целиком.

    Поиск сюда не входит намеренно: он сужает список материалов, а не то,
    что закупили.
    """

    materials_count = serializers.IntegerField()
    amount_kopecks = serializers.IntegerField()
    documents_count = serializers.IntegerField()
    suppliers_count = serializers.IntegerField()

    positions_count = serializers.IntegerField()
    # 97 из 402 на боевых данных. Без этого числа средняя цена выглядит
    # посчитанной по всему, что пришло на склад.
    free_positions_count = serializers.IntegerField()

    priced_count = serializers.IntegerField()
    unpriced_count = serializers.IntegerField()
    # Чем объясняются прочерки в колонках «Динамика» и «Поставщиков»:
    # у большинства наименований закупка была одна.
    with_history_count = serializers.IntegerField()
    multi_supplier_count = serializers.IntegerField()


class SupplyMaterialsSerializer(serializers.Serializer):
    synced_at = serializers.DateTimeField(allow_null=True)
    count = serializers.IntegerField()
    totals = SupplyMaterialsTotalsSerializer()
    coverage = SupplyMaterialsCoverageSerializer()
    results = SupplyMaterialRowSerializer(many=True)
    suppliers = FilterOptionSerializer(many=True)


class PurchaseSerializer(serializers.Serializer):
    """Одна закупка: документ целиком, а не строка в нём.

    Цена средневзвешенная, если строк было несколько: диметилфталат пришёл
    одной приёмкой двумя партиями — 2000 г по 40 копеек и 3000 г по 45.
    Показать их двумя закупками значило бы нарисовать скачок цены,
    которого не было.
    """

    document_id = serializers.IntegerField()
    number = serializers.CharField()
    moment = serializers.DateTimeField()
    supplier = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    amount_kopecks = serializers.IntegerField()
    price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    is_free = serializers.BooleanField()
    price_change = serializers.DecimalField(
        max_digits=16, decimal_places=8, allow_null=True
    )


class SupplierPriceSerializer(serializers.Serializer):
    """Что и почём брали у одного поставщика — строка сравнения.

    `above_best` считается от самой низкой **последней** цены среди
    поставщиков. Не от крайних цен вообще: у «Крышки флип-топ» разброс между
    первой и последней ценой одного «Лемуна» — 73%, и назвать это разницей
    между поставщиками значило бы предложить уйти от него к нему же.
    """

    supplier_id = serializers.IntegerField()
    name = serializers.CharField()
    supplies_count = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    amount_kopecks = serializers.IntegerField()
    avg_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    last_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    last_moment = serializers.DateTimeField(allow_null=True)
    above_best = serializers.DecimalField(
        max_digits=16, decimal_places=8, allow_null=True
    )


class SupplyMaterialDetailSerializer(serializers.Serializer):
    material = MaterialHeadSerializer()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    free_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    paid_quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    amount_kopecks = serializers.IntegerField()
    avg_price_kopecks = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    price_change = serializers.DecimalField(
        max_digits=16, decimal_places=8, allow_null=True
    )
    # Хронологически, от старой закупки к новой: история цен читается слева
    # направо, и «свежее сверху» ломало бы ровно то, ради чего её открыли.
    history = PurchaseSerializer(many=True)
    suppliers = SupplierPriceSerializer(many=True)
    # Остаток известен не по всем материалам. `null` честнее нуля,
    # который читается как «кончился».
    stock = StockSerializer(allow_null=True)
    # Запас в днях — то же число и тот же тип, что на «Материалах
    # в отгрузках»: вопрос разный («надолго ли хватит» против «пора ли
    # закупать»), а расчёт один, и разойтись он не имеет права.
    coverage = MaterialCoverageSerializer()
