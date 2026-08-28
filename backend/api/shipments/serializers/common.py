"""Общее для контрактов раздела: фильтры выборки и справочник каналов.

Сериализаторы ответов нужны не для валидации, а для схемы: из неё
генерируются типы фронтенда, и без них расхождение фронта с бэком
перестаёт ловиться на сборке.

Деньги уходят целыми копейками, удельные величины — строкой Decimal.
Рубли и проценты появляются только на экране: перевести их здесь значило бы
потерять знаки ровно там, где они значат разницу между «сошлось с учётом»
и «почти сошлось».
"""

from rest_framework import serializers


class SelectionQuerySerializer(serializers.Serializer):
    """Фильтры страницы раздела. Они же живут в адресной строке — ссылку
    можно переслать, и она откроется тем же, что человек видел.

    Общая часть у обеих страниц: период, канал, поиск и разбиение на страницы
    устроены одинаково. Разное — только допустимые сортировки и высота
    страницы, они задаются наследником.
    """

    date_from = serializers.DateField(required=False, allow_null=True)
    date_to = serializers.DateField(required=False, allow_null=True)
    channel_id = serializers.IntegerField(required=False, allow_null=True)
    search = serializers.CharField(required=False, allow_blank=True, default="")
    page = serializers.IntegerField(required=False, min_value=1, default=1)

    def validate(self, attrs):
        start, end = attrs.get("date_from"), attrs.get("date_to")
        if start and end and start > end:
            raise serializers.ValidationError(
                {"date_from": "Начало периода позже его конца."}
            )
        return attrs


class SalesChannelSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


