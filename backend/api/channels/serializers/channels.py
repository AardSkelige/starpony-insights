"""Контракт страницы «Каналы продаж».

Своё у неё против соседних страниц — две вещи.

**Чек приходит медианой вместе с разбросом и средним**, из которых получен:
у «Точки продаж» среднее 13 766 ₽ против медианы 2 772 ₽, и само расхождение
отвечает на вопрос, чем канал держится. Одно число этого не говорит.

**Ноль у чека — ответ, а не пробел.** У Instagram и Telegram медиана ровно
ноль: больше половины отгрузок ушли даром. `null` остаётся каналу,
у которого отгрузок нет вовсе, — эти два случая нельзя путать.
"""

from rest_framework import serializers

from api.channels.services.channels import DEFAULT_ORDERING, ORDERING
from api.common.serializers import SelectionQuerySerializer


class ChannelsQuerySerializer(SelectionQuerySerializer):
    """Выборка страницы: период, поиск, страница, порядок.

    Справочника для сужения здесь нет намеренно. У «Товаров в отгрузках»
    канал сужает выборку, потому что строка там — товар; здесь канал и есть
    строка, и фильтр по нему оставил бы в таблице ровно одну.
    """

    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


class ReceiptSerializer(serializers.Serializer):
    """Средний чек канала вместе с тем, из чего он получен."""

    # Медиана, а не среднее: одна отгрузка на 99 495 ₽ утаскивает среднее
    # «Точки продаж» впятеро. Спрашивают «сколько обычно».
    kopecks = serializers.IntegerField(allow_null=True)
    # Знаменатель медианы: по скольким отгрузкам она посчитана.
    shipments = serializers.IntegerField()
    min_kopecks = serializers.IntegerField(allow_null=True)
    max_kopecks = serializers.IntegerField(allow_null=True)
    # Среднее — только в объяснении, рядом с медианой.
    average_kopecks = serializers.IntegerField(allow_null=True)
    # Объясняет нулевую медиану: без этого числа «чек 0 ₽» читается
    # как сбой расчёта, а не как факт учёта.
    free_shipments = serializers.IntegerField()


class ChannelTopItemSerializer(serializers.Serializer):
    """Строка списка «кто покупает» и «что покупают».

    Один тип на оба списка: поля совпадают до буквы, и два близнеца в схеме
    дали бы фронтенду два типа, под которые пишутся два компонента.
    Так уже расходился блок «Склад».

    Имя не `ChannelShare`: такой компонент в схеме уже есть — доля канала
    в продажах товара на странице отгрузок. Генератор схемы предупреждает
    о столкновении, но собирает её всё равно, и фронтенд получил бы неверные
    типы, ничего об этом не узнав.
    """

    name = serializers.CharField()
    revenue_kopecks = serializers.IntegerField()
    share = serializers.DecimalField(max_digits=9, decimal_places=8, allow_null=True)
    # Подстрочник: «14 отгрузок» у покупателя, «12 наименований» у линейки.
    # Склоняется на сервере — склонятель один на проект (`core/text.py`),
    # и вторая копия правила на фронте разошлась бы с первой.
    note = serializers.CharField(allow_blank=True)


class ChannelTopSerializer(serializers.Serializer):
    """Крупнейшие плюс свёрнутый хвост: слагаемые обязаны складываться."""

    items = ChannelTopItemSerializer(many=True)
    rest_count = serializers.IntegerField()
    rest_revenue_kopecks = serializers.IntegerField()


class ChannelRowSerializer(serializers.Serializer):
    channel_id = serializers.IntegerField()
    name = serializers.CharField()
    # Номер цвета в палитре, 1…8. `null` — канал за пределами восьмёрки,
    # он рисуется приглушённым «Другим». Закреплён за каналом по выручке
    # за всю историю: сортировка не должна перекрашивать графики.
    slot = serializers.IntegerField(allow_null=True)

    shipments_count = serializers.IntegerField()
    revenue_kopecks = serializers.IntegerField()
    revenue_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )

    first_moment = serializers.DateTimeField()
    last_moment = serializers.DateTimeField()

    receipt = ReceiptSerializer()

    buyers_count = serializers.IntegerField()
    products_count = serializers.IntegerField()

    buyers = ChannelTopSerializer()
    products = ChannelTopSerializer()

    # Выручка канала по тем же корзинам, что и стопка наверху страницы:
    # разбор строки показывает ряд одного канала, и границы столбиков
    # у них обязаны совпадать.
    dynamics = serializers.ListField(child=serializers.IntegerField())


class DynamicsSeriesSerializer(serializers.Serializer):
    channel_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()
    slot = serializers.IntegerField(allow_null=True)
    revenue_kopecks = serializers.IntegerField()


class DynamicsPointSerializer(serializers.Serializer):
    """Один столбик. Границы обе: одна дата рядом с подписью «по неделям»
    читается как день — так и вышло при первом показе на соседней странице."""

    start = serializers.DateField()
    end = serializers.DateField()
    # Столько же чисел, сколько серий, и в том же порядке: слагаемые
    # складываются в высоту столбика.
    values = serializers.ListField(child=serializers.IntegerField())


class DynamicsSerializer(serializers.Serializer):
    """Выручка по каналам во времени — стопка столбиков."""

    step = serializers.CharField()
    # Подпись говорит, чем измерен один столбик. Приходит с сервера, потому
    # что шаг выбирает сервер, и два места, решающие это по-своему, разъедутся.
    step_label = serializers.CharField()
    series = DynamicsSeriesSerializer(many=True)
    points = DynamicsPointSerializer(many=True)


class ChannelStandingSerializer(serializers.Serializer):
    """Канал в полосах над таблицей: две доли одного канала рядом.

    Отдельный тип, а не строка таблицы: полосам не нужны ни списки
    покупателей, ни ряд по времени, а строк тут всегда все — поиск и страница
    их не сужают.
    """

    channel_id = serializers.IntegerField()
    name = serializers.CharField()
    slot = serializers.IntegerField(allow_null=True)
    revenue_kopecks = serializers.IntegerField()
    revenue_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    shipments_count = serializers.IntegerField()
    # Доля в отгрузках. Расхождение с долей в деньгах — вопрос, ради которого
    # страницу открывают: канал берёт чеком или числом.
    shipments_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class ChannelsTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска."""

    channels_count = serializers.IntegerField()
    shipments_count = serializers.IntegerField()
    revenue_kopecks = serializers.IntegerField()
    revenue_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    # Через объединение, а не сложением колонки: один покупатель приходит
    # через несколько каналов и был бы посчитан дважды.
    buyers_count = serializers.IntegerField()
    products_count = serializers.IntegerField()


class ChannelsCoverageSerializer(serializers.Serializer):
    """Сводка — про выборку отгрузок целиком. Поиск её не трогает."""

    channels_count = serializers.IntegerField()
    shipments_count = serializers.IntegerField()
    revenue_kopecks = serializers.IntegerField()
    # Отгрузки без канала: одна из 306 на боевых данных. Именно они
    # объясняют, почему итог таблицы меньше числа отгрузок в учёте.
    unassigned_shipments_count = serializers.IntegerField()
    unassigned_revenue_kopecks = serializers.IntegerField()
    # Отгрузки, ушедшие даром: 46 из 306. Без них нулевая медиана чека
    # у двух каналов выглядит сбоем расчёта.
    free_shipments_count = serializers.IntegerField()
    buyers_count = serializers.IntegerField()
    products_count = serializers.IntegerField()


class ChannelsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    synced_at = serializers.DateTimeField(allow_null=True)
    totals = ChannelsTotalsSerializer()
    coverage = ChannelsCoverageSerializer()
    standings = ChannelStandingSerializer(many=True)
    dynamics = DynamicsSerializer()
    results = ChannelRowSerializer(many=True)
