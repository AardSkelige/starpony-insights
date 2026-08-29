"""Контракт запроса раздела отгрузок — то, чего нет у соседних разделов.

Общее (период, поиск, страница, остаток, значение справочника) живёт
в `api/common/serializers.py`: у приёмок оно ровно такое же. Здесь только
канал продаж — поле, которого у приёмки не существует.
"""

from rest_framework import serializers

from api.common.serializers import SelectionQuerySerializer


class ShipmentQuerySerializer(SelectionQuerySerializer):
    """Выборка отгрузок: общее плюс канал продаж.

    Наследование, а не поле в общем классе: приняв `channel_id` на странице
    приёмок, сервер молча проигнорировал бы его — и ссылка «приёмки по Озону»
    открывалась бы полным списком, выглядя отфильтрованной.
    """

    channel_id = serializers.IntegerField(required=False, allow_null=True)
