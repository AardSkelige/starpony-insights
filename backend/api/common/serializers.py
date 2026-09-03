"""Контракты, общие для разделов: выборка, справочник фильтра, остаток.

Сериализаторы ответов нужны не для валидации, а для схемы: из неё
генерируются типы фронтенда, и без них расхождение фронта с бэком
перестаёт ловиться на сборке.

Деньги уходят целыми копейками, удельные величины — строкой Decimal.
Рубли и проценты появляются только на экране: перевести их здесь значило бы
потерять знаки ровно там, где они значат разницу между «сошлось с учётом»
и «почти сошлось».
"""

from rest_framework import serializers

from api.common.selection import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


class SelectionQuerySerializer(serializers.Serializer):
    """Фильтры страницы. Они же живут в адресной строке — ссылку можно
    переслать, и она откроется тем же, что человек видел.

    Общая часть у всех страниц: период, поиск и разбиение на страницы
    устроены одинаково. Разное задаётся наследником — справочник, которым
    сужают выборку (`channel_id` у отгрузок, `supplier_id` у приёмок),
    и допустимые сортировки.
    """

    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    # Высота страницы одна на все разделы, и слишком большая отклоняется,
    # а не обрезается молча: ответ на `?page_size=1000` должен сказать, что
    # столько не отдаём, — иначе человек решит, что строк действительно 200.
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


class FilterOptionSerializer(serializers.Serializer):
    """Значение справочника в выпадающем списке фильтров.

    Один тип на канал продаж и на поставщика: в списке они устроены
    одинаково — идентификатор и подпись, — а два одинаковых типа в схеме
    дали бы фронтенду два компонента вместо одного поля фильтра.
    """

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


class MaterialHeadSerializer(serializers.Serializer):
    """Шапка разбора строки: чем именно является материал.

    Один сериализатор на оба раздела. Поля у них совпадали до буквы, и схема
    из-за двойника выдавала предупреждение «два компонента с одним именем
    и разными телами» — то есть фронтенд получил бы неверные типы, ничего
    об этом не узнав.
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    article = serializers.CharField(allow_blank=True)
    code = serializers.CharField(allow_blank=True)
    uom = serializers.CharField(allow_blank=True)


class MaterialCoverageSerializer(serializers.Serializer):
    """На сколько хватит остатка при нынешнем расходе.

    Один тип на три раздела: «Материалы в отгрузках» отвечают им на «надолго
    ли хватит», «Материалы в приёмках» — на «пора ли закупать», «Расчёт
    производства» — на «пора ли варить». Вопрос разный, число одно,
    и разойтись оно не имеет права.

    Первая половина порога закупки (`PRD.md` §5.9): `minimumBalance` задан
    у десяти позиций сырья из трёхсот с лишним, а расход за период против
    свободного остатка берётся из фактов учёта по всем.

    **Это не прогноз**, и подсказка на экране обязана это сказать: средний
    расход выбранного периода, а не тренд. Меняешь период — меняется число.
    """

    # Расход за период — числитель формулы. Приходит вместе с ответом,
    # а не берётся из строки: у «Материалов в приёмках» в строке лежит
    # закупленное, а не израсходованное.
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)
    # Средний расход за сутки — рядом с ответом, чтобы формула собиралась
    # из полученного, а не пересчитывалась на фронте.
    per_day = serializers.DecimalField(max_digits=18, decimal_places=3)
    days_of_period = serializers.IntegerField()
    # `null` — остатка в отчёте нет (36 материалов из 161) или расхода
    # за период не было. Ноль означал бы «кончился», а это другое
    # утверждение об учёте.
    days_left = serializers.IntegerField(allow_null=True)
    # `none` / `ok` / `low` / `critical`. Считается на сервере: пороги
    # и текст предупреждения обязаны меняться вместе.
    level = serializers.CharField()


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
    days = serializers.DecimalField(max_digits=8, decimal_places=1, allow_null=True)
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


class LeadTimeSerializer(SpanSerializer):
    """Срок от заказа до прихода товара.

    Переехал сюда из «Поставщиков», когда понадобился «Расчёту
    производства»: там спрашивают «кого торопить», здесь — «успеет ли сырьё
    к партии». Вопрос разный, число одно, и два типа в схеме дали бы
    фронтенду два компонента под одно и то же.
    """

    measurements = serializers.IntegerField(source="pairs")
    # Приёмки, у которых заказа в зеркале нет. Показывается словами:
    # «срок по 12 приёмкам из 14» честнее, чем молчаливая медиана по части.
    unlinked = serializers.IntegerField()


class MaterialPathSerializer(serializers.Serializer):
    """Один путь до материала и сколько пришло именно им.

    Количество обязательно: без него путь говорит «через замес и через
    розлив», но не отвечает, чего сколько, — а объяснение, которое
    не складывается обратно в объясняемое число, объяснением не является.
    """

    chain = serializers.ListField(child=serializers.CharField())
    quantity = serializers.DecimalField(max_digits=18, decimal_places=6)


class MaterialPriceSerializer(serializers.Serializer):
    """Откуда взялась цена: документ, дата, поставщик.

    Число, посчитанное по цене, обязано назвать её источник. Иначе колонка
    «Стоимость» остаётся суммой, за которую никто не отвечает.
    """

    price_kopecks = serializers.DecimalField(max_digits=18, decimal_places=6)
    moment = serializers.DateTimeField()
    document_number = serializers.CharField()
    supplier = serializers.CharField()


class ConsignmentOutstandingSerializer(serializers.Serializer):
    """Вся картина реализации — состояние на сегодня, а не итог периода.

    Ради одного вычитания: отгружено на реализацию минус подтверждено
    отчётами комиссионера = столько лежит у комиссионеров прямо сейчас.
    Это и есть сумма, на которую «Прибыльность» отстаёт от отгрузочных
    страниц; увидев её, человек перестаёт считать расхождение сбоем расчёта.

    Один тип на «Каналы продаж» и «Товары в отгрузках»: вычитание у них
    одно и то же, и разойтись оно не имеет права — на «Прибыльности»
    с ним сверяют обе страницы.

    **Периода здесь нет намеренно** — почему, написано в
    `core/services/consignment.py`.
    """

    shipped_kopecks = serializers.IntegerField()
    reported_kopecks = serializers.IntegerField()
    pending_kopecks = serializers.IntegerField()


class ConsignmentShareSerializer(serializers.Serializer):
    """Сколько из показанной выручки — товар на реализации, а не продажа.

    Один тип на «Каналы продаж» и «Товары в отгрузках»: вопрос у них разный —
    «на чём держится канал» и «сколько продали этого товара», — а оговорка
    одна, и разойтись она не имеет права.

    **Оговорка не косметическая.** По договору комиссии товар уходит
    комиссионеру на склад и становится продажей только с приходом отчёта;
    до этого он может вернуться. У «Точки продаж» так 87 % выручки,
    у Telegram 97 % — вывод «канал приносит больше всех» держится на складе
    комиссионера.

    **Это не размер расхождения с «Прибыльностью».** Здесь вся реализация
    показанной выборки (452 696 ₽ на 03.09), а расходятся страницы на её
    непокрытую отчётами часть за всё время (281 126 ₽) — её считает
    `consignment.outstanding`, и живёт она в сводке под таблицей.
    """

    total_kopecks = serializers.IntegerField()
    consignment_kopecks = serializers.IntegerField()
    # `null` — выручки нет вовсе, и доля не считается. Ноль означал бы
    # «реализации нет», а это другое утверждение.
    fraction = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    # `default` / `warning`. Порог считает сервер: раскраска полосы и подпись
    # рядом с ней обязаны меняться вместе.
    tone = serializers.CharField()
