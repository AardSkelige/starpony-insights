"""Контракт страницы «Сроки оплаты».

Отличие от соседних страниц — в том, что здесь **три суммы вместо одной**,
и каждая обязана прийти отдельным полем. Дебиторка, расчёты через площадку
и товар на реализации складываются в одно число только по ошибке: на 02.09
это 123 044 ₽, 314 470 ₽ и 452 696 ₽, и лишь первое означает «нам должны».

`null` у срока и отсрочки — рабочее состояние, а не пробел. Отсрочка
не проставлена ни у одного из 107 контрагентов, поэтому срок оплаты
посчитать не из чего; ноль означал бы «платят в день отгрузки»,
а это другое утверждение об учёте.
"""

from rest_framework import serializers

from api.common.serializers import SelectionQuerySerializer
from api.deadlines.services.selection import DEFAULT_ORDERING, ORDERING


class DeadlinesQuerySerializer(SelectionQuerySerializer):
    """Выборка страницы: поиск, страница, порядок.

    **Периода здесь нет намеренно** — поля объявлены `None`, и DRF убирает
    их из контракта. Долг это состояние на сегодня, а не итог за отрезок:
    выбери человек «август», и долг возрастом 93 дня исчез бы с экрана.
    Оставить параметры «на всякий случай» значило бы отдать в схему ссылку,
    которая выглядит рабочей и показывает не то, что обещает.
    """

    date_from = None
    date_to = None

    ordering = serializers.ChoiceField(
        choices=sorted(ORDERING), required=False, default=DEFAULT_ORDERING
    )


class AgeShelfSerializer(serializers.Serializer):
    """Полка возраста: сколько денег лежит без движения столько-то дней.

    Полки упорядочены и приходят всегда все четыре, включая пустые:
    пропущенная корзина превращает шкалу в произвольный набор столбиков,
    а «между 15 и 60 днями ничего нет» — это ответ, и он должен быть виден.
    """

    key = serializers.CharField()
    label = serializers.CharField()
    # Потолок полки в днях; `null` у последней — у неё его нет.
    # Приходит, чтобы подпись на экране собиралась из данных, а не повторяла
    # число, записанное на сервере.
    up_to_days = serializers.IntegerField(allow_null=True)
    # Уложился ли долг этой полки в обещанный цикл выплаты. Считается
    # на сервере рядом с границами: два места, знающие про 30 дней,
    # однажды разойдутся, и разойдутся тихо.
    fresh = serializers.BooleanField()
    count = serializers.IntegerField()
    debt_kopecks = serializers.IntegerField()
    share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )


class DebtGroupSerializer(serializers.Serializer):
    """Группа срока: просрочено, скоро истекает, в норме, без отсрочки.

    Сегодня всё до последнего документа лежит в «без оформленной отсрочки».
    Группы включатся сами, когда в учёте появятся дни отсрочки, — поэтому
    поле есть в контракте с первого дня, а не добавляется потом.
    """

    key = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    debt_kopecks = serializers.IntegerField()


class DeadlineRowSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    name = serializers.CharField()
    # Расчёты через площадку: выплата приходит реестром и в учёт не заводится.
    # Признак из учёта — группа контрагента «маркетплейсы».
    is_marketplace = serializers.BooleanField()
    deferral_days = serializers.IntegerField(allow_null=True)

    debt_kopecks = serializers.IntegerField()
    debt_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    documents_count = serializers.IntegerField()

    # Возраст старейшего непогашенного документа — то, по чему решают,
    # звонить сегодня или подождать.
    oldest_age_days = serializers.IntegerField()
    newest_age_days = serializers.IntegerField()
    aging = AgeShelfSerializer(many=True)

    # Чем возник долг: отгрузками или отчётами комиссионера. Без этого
    # «2 документа на 98 125 ₽» у Каприоля выглядит ошибкой рядом
    # с 16 отгрузками в разборе.
    kinds = serializers.DictField(child=serializers.IntegerField())
    channels = serializers.ListField(child=serializers.CharField())
    groups = DebtGroupSerializer(many=True)


class DeadlinesTotalsSerializer(serializers.Serializer):
    """Итог под таблицей — про то, что в ней видно, с учётом поиска."""

    counterparties_count = serializers.IntegerField()
    documents_count = serializers.IntegerField()
    debt_kopecks = serializers.IntegerField()
    debt_share = serializers.DecimalField(
        max_digits=9, decimal_places=8, allow_null=True
    )
    # `null` — строк нет вовсе; ноль означал бы «долг сегодняшний».
    oldest_age_days = serializers.IntegerField(allow_null=True)


class DeadlinesCoverageSerializer(serializers.Serializer):
    """Вся картина расчётов. Поиск её не трогает.

    Три суммы рядом отвечают на вопрос, который иначе задают вслух каждый
    раз: почему «не оплачено» в учёте и «нам должны» — разные числа.
    """

    counterparties_count = serializers.IntegerField()
    documents_count = serializers.IntegerField()
    debt_kopecks = serializers.IntegerField()

    marketplaces_count = serializers.IntegerField()
    marketplace_documents_count = serializers.IntegerField()
    marketplace_kopecks = serializers.IntegerField()

    consignment_count = serializers.IntegerField()
    consignment_kopecks = serializers.IntegerField()
    # По скольким комиссионерам. Не всегда совпадает с числом строк таблицы:
    # у комиссионера с оплаченными отчётами долга нет, а товар на реализации
    # есть — и сумма в сводке иначе была бы больше найденного в разборе строк.
    consignment_counterparties_count = serializers.IntegerField()

    # Объясняет, почему на экране нет ни «просрочено», ни «в норме»:
    # без отсрочки срока оплаты не существует.
    with_deferral_count = serializers.IntegerField()
    counterparties_total = serializers.IntegerField()

    # Просроченное и подходящее к сроку — по всей дебиторке. Сегодня нули:
    # отсрочки нет ни у кого. Появится она — появятся и числа, без правок.
    overdue_count = serializers.IntegerField()
    overdue_kopecks = serializers.IntegerField()
    soon_count = serializers.IntegerField()
    soon_kopecks = serializers.IntegerField()


class DeadlinesSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    synced_at = serializers.DateTimeField(allow_null=True)
    aging = AgeShelfSerializer(many=True)
    totals = DeadlinesTotalsSerializer()
    coverage = DeadlinesCoverageSerializer()
    # Площадок две, и разбивать их на страницы нечего: блок под таблицей
    # показывает их целиком.
    marketplaces = DeadlineRowSerializer(many=True)
    results = DeadlineRowSerializer(many=True)


class DeadlineDocumentSerializer(serializers.Serializer):
    number = serializers.CharField()
    kind = serializers.CharField()
    kind_label = serializers.CharField()
    moment = serializers.DateTimeField()
    age_days = serializers.IntegerField()

    total_kopecks = serializers.IntegerField()
    paid_kopecks = serializers.IntegerField()
    debt_kopecks = serializers.IntegerField()

    due_date = serializers.DateField(allow_null=True)
    days_left = serializers.IntegerField(allow_null=True)
    group = serializers.CharField()
    # Формула у расчётного числа. Без отсрочки говорит именно это —
    # «посчитать не из чего», а не молчит.
    explanation = serializers.CharField()

    channel = serializers.CharField(allow_blank=True)
    description = serializers.CharField(allow_blank=True)


class ConsignmentSerializer(serializers.Serializer):
    """Товар, отгруженный по договору комиссии. Долгом не считается.

    Ноль — обычный случай: договор комиссии есть у двоих из 107
    контрагентов. Показывается ради одного вопроса — «почему долг такой
    маленький при таких отгрузках».
    """

    count = serializers.IntegerField()
    kopecks = serializers.IntegerField()
    contracts = serializers.ListField(child=serializers.CharField())
    first_moment = serializers.DateField(allow_null=True)


class DeadlineDetailSerializer(serializers.Serializer):
    agent_id = serializers.IntegerField()
    name = serializers.CharField()
    is_marketplace = serializers.BooleanField()
    deferral_days = serializers.IntegerField(allow_null=True)

    debt_kopecks = serializers.IntegerField()
    documents_count = serializers.IntegerField()
    oldest_age_days = serializers.IntegerField()

    documents = DeadlineDocumentSerializer(many=True)
    # Хвост сворачивается, но не выбрасывается: иначе показанные слагаемые
    # перестают сходиться с суммой строки.
    rest_count = serializers.IntegerField()
    rest_debt_kopecks = serializers.IntegerField()

    consignment = ConsignmentSerializer()
