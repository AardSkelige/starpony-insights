"""Контракт «Расчёта производства». Из него же берутся типы фронтенда.

Два ответа на два звена цепочки: что кончается — и что нужно закупить
под выбранную партию. Разными запросами, потому что меняются они по разным
причинам: верхний список зависит от периода и горизонта, нижний — от того,
что человек отобрал. Слей их в один — правка количества в партии
перезапрашивала бы весь каталог.

Расчётные числа отдаются **составляющими, а не готовым текстом**
(`CLAUDE.md` §4): «произвести 61» приходит вместе с темпом продаж, горизонтом
и остатком, из которых получено, — иначе формулу пришлось бы собирать
на фронте, то есть считать второй раз и другим кодом.
"""

from rest_framework import serializers

from api.common.serializers import (
    LeadTimeSerializer,
    MaterialCoverageSerializer,
    MaterialPathSerializer,
    MaterialPriceSerializer,
)
from api.production.services.selection import (
    DEFAULT_HORIZON,
    MAX_HORIZON,
    MIN_HORIZON,
)


class ProductsQuerySerializer(serializers.Serializer):
    """Запрос верхнего звена: за какой период смотрим спрос и на сколько варим.

    `page` и `page_size` не наследуются от `SelectionQuerySerializer`
    намеренно: разбиения на страницы у раздела нет (см. `services/selection.py`),
    и объявить параметры, которые ничего не делают, значило бы соврать
    в `/api/docs`.
    """

    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    # На сколько дней вперёд производим. Он же — страховой запас из `PRD.md`
    # §5.9: вместо числа, придуманного в коде, человек выбирает его сам
    # и видит последствия на живых числах.
    horizon = serializers.IntegerField(
        required=False,
        min_value=MIN_HORIZON,
        max_value=MAX_HORIZON,
        default=DEFAULT_HORIZON,
    )

    def validate(self, attrs):
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_from": "Начало периода позже его конца."}
            )
        return attrs


class BatchQuerySerializer(ProductsQuerySerializer):
    """Запрос нижнего звена: состав партии.

    `item` повторяется — по строке на позицию: `item=200.040.05:200`
    или `item=200.040.05` без количества. В адресной строке, а не в теле
    запроса, чтобы расчёт можно было переслать ссылкой и вернуть кнопкой
    «назад».

    **Наследует период и горизонт**, потому что позиция без количества
    означает «посчитай сам»: предложение считается из продаж за период
    и выбранного срока — теми же числами, что в списке товаров, и той же
    формулой. Поиск наследуется тоже, но на разрешение количеств не влияет
    (`payload.resolve`): партия собрана раньше, чем человек начал искать.
    """

    item = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        default=list,
        help_text=(
            "Позиция партии: «артикул:количество» либо «артикул» — тогда "
            "количество считается по горизонту."
        ),
    )


class ProductRowSerializer(serializers.Serializer):
    """Товар: надолго ли хватит и сколько варить."""

    product_id = serializers.IntegerField()
    article = serializers.CharField()
    name = serializers.CharField()
    # Путь папки — по нему на экране собираются линейки продукции: семь групп
    # на 57 товаров, и без них список читается как одна простыня.
    folder = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)

    # `null` — строки остатка в отчёте нет вовсе. Ноль здесь означал бы
    # «кончился», а это другое утверждение об учёте.
    available = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    coverage = MaterialCoverageSerializer()

    # `null` — считать не из чего: товар не продавался за период либо
    # остаток неизвестен. Ноль значил бы «производить не надо».
    suggested = serializers.IntegerField(allow_null=True)
    horizon = serializers.IntegerField()

    # Техкарты нет — развернуть до сырья нечем. Такой один из 57, и сказать
    # об этом надо словами: молча пропущенная строка выглядит как забытая.
    has_plan = serializers.BooleanField()

    # Сколько обещано под заказы покупателей. Ноль у большинства — резерв
    # ставят галочкой в заказе, и ставить её начали недавно.
    #
    # Показывается только когда больше нуля: строка «в резерве 0» есть
    # у всех и не сообщает ничего. Зато при ненулевом объясняет, почему
    # свободный остаток меньше складского, — без неё «остаток 5» при шести
    # на складе выглядит ошибкой данных.
    reserved = serializers.DecimalField(max_digits=18, decimal_places=3)


class ProductsSummarySerializer(serializers.Serializer):
    """Итог верхнего списка. Считается по показанному, а не по всей базе.

    Знаменатель обязан сужаться поиском вместе со строками: иначе, найдя
    один товар, человек увидит «33 из 57 кончаются» — число про множество,
    которого на экране нет (`DESIGN.md` §8).
    """

    products_count = serializers.IntegerField()
    # Сколько кончается в ближайшие две недели — порог `coverage.CRITICAL_DAYS`,
    # общий с материалами.
    critical_count = serializers.IntegerField()
    # По скольким запас неизвестен. Рядом с предыдущим числом обязательно:
    # «кончается 33 из 57» без него читается как «остальные 24 в порядке».
    unknown_count = serializers.IntegerField()
    without_plan_count = serializers.IntegerField()


class ProductsSerializer(serializers.Serializer):
    """Ответ верхнего звена целиком."""

    rows = ProductRowSerializer(many=True)
    summary = ProductsSummarySerializer()
    horizon = serializers.IntegerField()
    synced_at = serializers.DateTimeField(allow_null=True)


class BatchLineSerializer(serializers.Serializer):
    """Строка партии — включая ту, что в расчёт не пошла.

    Непринятая строка не выбрасывается: сломанная ссылка и опечатка
    в артикуле выглядят одинаково, а «посчитали по трём товарам из четырёх»
    ничем не отличается на вид от «посчитали по всем».
    """

    article = serializers.CharField()
    # `null` — количество предложить не из чего, и человек его не вводил.
    # Ноль означал бы «произвести ноль», а это другое утверждение.
    quantity = serializers.IntegerField(allow_null=True)
    # `null` — артикула нет в учёте вовсе. У остальных заполнено даже при
    # проблеме: «Peachy Banana — в архиве» человек поймёт, «200.008.05 —
    # в архиве» отправит его в учёт за названием.
    product_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_blank=True)
    # `null` — строка в расчёт пошла. Иначе `unknown` / `archived` /
    # `no_plan` / `no_quantity`.
    problem = serializers.CharField(allow_null=True)


class BatchSourceSerializer(serializers.Serializer):
    """Из какого товара партии сколько этого материала пришло.

    Не `MaterialSource` «Материалов в отгрузках»: там источник — проданное
    изделие, и рядом едут проданное количество, его единица и пути. Одно имя
    на два разных тела схема встречает предупреждением, а фронтенд —
    неверными типами, ничего об этом не узнав.
    """

    product_id = serializers.IntegerField()
    name = serializers.CharField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class NeedSerializer(serializers.Serializer):
    """Материал под партию: сколько нужно, что есть, чего не хватает."""

    product_id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)

    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)
    available = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    # `null` — остаток неизвестен, вычитать не из чего. Ноль означал бы
    # «всё есть», а это другое утверждение об учёте.
    shortage = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )
    # Что останется после партии. Отрицательным не бывает: недостающее
    # уезжает в `shortage`, а здесь остаётся ноль.
    after = serializers.DecimalField(
        max_digits=18, decimal_places=6, allow_null=True
    )

    # Неснижаемый остаток из карточки — ручной порог владельца. Задан
    # у десяти позиций сырья; `null` у остальных.
    min_balance = serializers.DecimalField(
        max_digits=18, decimal_places=3, allow_null=True
    )
    # Материал в архиве, а техкарта его требует: карту забыли поправить
    # вместе с линейкой. Не пробел в учёте, а рассогласование — и молчать
    # о нём нельзя: остатка по архивному МойСклад не отдаёт, и строка
    # выглядела бы загадочным «не знаем».
    archived = serializers.BooleanField()
    # Остаток ниже минимума уже сейчас — состояние склада, к этой партии
    # отношения не имеющее.
    below_min_now = serializers.BooleanField()
    # Станет ниже минимума из-за этой партии. Отдельно от предыдущего:
    # «хватает, но останется 16 г при минимуме 1000» — это не «не хватает»
    # и не «всё хорошо».
    below_min_after = serializers.BooleanField()

    price = MaterialPriceSerializer(allow_null=True)
    # Во сколько обойдётся докупка недостающего. `null` — цены нет либо
    # докупать нечего.
    cost_kopecks = serializers.IntegerField(allow_null=True)
    lead_time = LeadTimeSerializer()
    supplier = serializers.CharField(allow_blank=True)

    # Объяснение числа: из каких товаров партии и какими цепочками техкарт
    # оно набралось. Сумма по путям равна `quantity`.
    via = MaterialPathSerializer(many=True)
    sources = BatchSourceSerializer(many=True)


class BatchSummarySerializer(serializers.Serializer):
    """Итог по партии — то, ради чего страницу открывали."""

    products_count = serializers.IntegerField()
    units_count = serializers.IntegerField()
    materials_count = serializers.IntegerField()

    shortages_count = serializers.IntegerField()
    # Сумма закупки — по тем недостающим позициям, у которых известна цена.
    # Рядом обязательно `priced_shortages_count`: иначе сумма выглядит итогом
    # по всем недостающим, а она итог по части (`DESIGN.md` §8).
    purchase_kopecks = serializers.IntegerField()
    priced_shortages_count = serializers.IntegerField()
    # Самый долгий срок среди недостающего: партия начнётся не раньше, чем
    # приедет последнее. `null` — сроков нет ни у одного поставщика.
    max_lead_time_days = serializers.DecimalField(
        max_digits=6, decimal_places=1, allow_null=True
    )
    # По скольким недостающим срок известен. Рядом со сроком обязательно:
    # он считается только там, где известен поставщик, а тот берётся
    # из последней приёмки (`DESIGN.md` §8).
    timed_shortages_count = serializers.IntegerField()

    unknown_stock_count = serializers.IntegerField()
    archived_count = serializers.IntegerField()
    below_min_now_count = serializers.IntegerField()
    below_min_after_count = serializers.IntegerField()


class BatchSerializer(serializers.Serializer):
    """Ответ нижнего звена целиком."""

    lines = BatchLineSerializer(many=True)
    materials = NeedSerializer(many=True)
    summary = BatchSummarySerializer()
    synced_at = serializers.DateTimeField(allow_null=True)
