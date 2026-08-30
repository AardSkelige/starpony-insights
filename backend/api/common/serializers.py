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

    Один тип на два раздела: «Материалы в отгрузках» отвечают им на «надолго
    ли хватит», «Материалы в приёмках» — на «пора ли закупать». Вопрос разный,
    число одно, и разойтись оно не имеет права.

    Первая половина порога закупки (`PRD.md` §5.9): `minimumBalance` пуст
    у всех 314 позиций, а расход за период против свободного остатка
    берётся из фактов учёта.

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
