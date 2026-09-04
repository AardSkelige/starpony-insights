"""Контракт главной.

**Почти всё поле здесь `allow_null`, и это не осторожность.** Плитка, к странице
которой у человека нет доступа, приходит пустой — не пустым списком, а `null`:
пустой список означал бы «посчитали и не нашли ничего», а это другой ответ.
Различить их обязан фронт, иначе Яна увидит «маржи нет» вместо «маржа не для вас».

Проценты — `DecimalField`, а не `float`: доля изменения складывается и
сравнивается на экране, и двоичная погрешность здесь превратилась бы
в «+148.00000000000003 %».
"""

from rest_framework import serializers


class HomePeriodSerializer(serializers.Serializer):
    """Окно страницы. Приходит с сервера, потому что сервер его и выбрал.

    Считать «последний полный месяц» на фронте значило бы завести вторую
    арифметику календаря — ту самую, что ошибается на декабре.
    """

    # Три формы месяца: именительный, родительный и дательный у предыдущего.
    # Склоняет сервер — на фронте иначе завелась бы вторая таблица месяцев.
    label = serializers.CharField()
    label_of = serializers.CharField()
    first = serializers.DateField()
    last = serializers.DateField()
    earlier_label = serializers.CharField()
    earlier_label_to = serializers.CharField()
    # Идущий месяц: `null` первого числа, когда его ещё нет.
    running_label = serializers.CharField(allow_null=True)
    running_days = serializers.IntegerField()
    running_of_days = serializers.IntegerField()


class HomeFoundSerializer(serializers.Serializer):
    """Одна найденная позиция: что именно и почему попало."""

    name = serializers.CharField()
    note = serializers.CharField()


class HomeSignalSerializer(serializers.Serializer):
    key = serializers.CharField()
    # Две подписи вместо одной: утверждение обязано менять форму вместе
    # с ответом. «резерв больше остатка» рядом с зелёной галочкой читается
    # как «резерв больше остатка — и это хорошо».
    label = serializers.CharField()
    label_clean = serializers.CharField()
    # Пояснение тоже в двух формах: «обещано ровно то, что есть» рядом
    # с «резерв в заказах превышает остаток» противоречит само себе.
    note = serializers.CharField()
    note_clean = serializers.CharField()
    count = serializers.IntegerField()
    # Что именно нашлось. Без списка переход в раздел показывает страницу,
    # а не проблему: человек ищет двадцать одну позицию среди пятидесяти.
    items = HomeFoundSerializer(many=True)
    # Ссылка приходит с сервера вместе с сигналом: путь и наложенная
    # сортировка — часть ответа «куда с этим идти», а не знание компонента.
    route = serializers.CharField()
    tone = serializers.ChoiceField(choices=["ok", "warn", "bad"])


class HomeSyncTroubleSerializer(serializers.Serializer):
    """Синхронизация отстала. `hours = -1` — не отрабатывала ни разу."""

    kind = serializers.CharField()
    label = serializers.CharField()
    usual = serializers.CharField()
    affects = serializers.CharField()
    hours = serializers.IntegerField()


class HomeListRowSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.IntegerField()
    note = serializers.CharField()


class HomeMisplacedSerializer(serializers.Serializer):
    lost_kopecks = serializers.IntegerField()
    lost_positions = serializers.IntegerField()
    frozen_kopecks = serializers.IntegerField()
    frozen_positions = serializers.IntegerField()
    stock_kopecks = serializers.IntegerField()
    # Окна приходят числами, чтобы подпись на экране собиралась из них,
    # а не повторяла их прописью: разойдись они, карточка сообщала бы
    # про шестьдесят дней, считая по девяноста.
    demand_days = serializers.IntegerField()
    material_days = serializers.IntegerField()
    to_brew = HomeListRowSerializer(many=True)
    lying_still = HomeListRowSerializer(many=True)
    # Полные списки для панели «показать все»: «173 позиции» — первое число,
    # о котором спрашивают «а что за 173», и страницы с таким же отбором
    # в проекте нет.
    lost_all = HomeListRowSerializer(many=True)
    frozen_all = HomeListRowSerializer(many=True)


class HomeFigureSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    value = serializers.IntegerField()
    earlier = serializers.IntegerField()
    # `null` — прошлый месяц был нулевым, и роста «с нуля» в процентах нет.
    change = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    unit = serializers.ChoiceField(choices=["money", "count", "percent"])


class HomeMonthSerializer(serializers.Serializer):
    start = serializers.DateField()
    end = serializers.DateField()
    revenue_kopecks = serializers.IntegerField()
    # Идущий месяц: рисуется бледным и в сравнения не входит.
    partial = serializers.BooleanField()


class HomePulseSerializer(serializers.Serializer):
    """Два множества разведены по группам — сложить их нельзя.

    `shipped` — документы: сколько увезли. `sold` — отчёт прибыльности:
    сколько из увезённого стало выручкой. Разница между ними — товар,
    ушедший по договору комиссии, и она названа отдельным числом,
    а не оставлена читателю на вычитание.
    """

    shipped = HomeFigureSerializer(many=True)
    sold = HomeFigureSerializer(many=True)
    consignment_kopecks = serializers.IntegerField()
    months = HomeMonthSerializer(many=True)


class HomeMarginSerializer(serializers.Serializer):
    name = serializers.CharField()
    revenue_kopecks = serializers.IntegerField()
    # Сотые доли процента: 8689 — это 86,89 %. Целым, чтобы не тащить
    # дробь через JSON там, где она всё равно округляется при показе.
    margin = serializers.IntegerField()
    quantity = serializers.DecimalField(max_digits=18, decimal_places=3)


class HomeChangeSerializer(serializers.Serializer):
    name = serializers.CharField()
    delta_kopecks = serializers.IntegerField()
    now_kopecks = serializers.IntegerField()
    earlier_kopecks = serializers.IntegerField()


class HomeChannelSerializer(serializers.Serializer):
    name = serializers.CharField()
    revenue_kopecks = serializers.IntegerField()
    documents = serializers.IntegerField()


class HomeSerializer(serializers.Serializer):
    period = HomePeriodSerializer()
    # `false` — синхронизация не отрабатывала ни разу. Тогда нули в счётчиках
    # означают незнание, а не благополучие, и блок обязан сказать это словами.
    known = serializers.BooleanField()
    signals = HomeSignalSerializer(many=True)
    sync_trouble = HomeSyncTroubleSerializer(allow_null=True)
    misplaced = HomeMisplacedSerializer(allow_null=True)
    pulse = HomePulseSerializer(allow_null=True)
    margins = HomeMarginSerializer(many=True, allow_null=True)
    changes = HomeChangeSerializer(many=True, allow_null=True)
    channels = HomeChannelSerializer(many=True, allow_null=True)
    synced_at = serializers.DateTimeField(allow_null=True)
