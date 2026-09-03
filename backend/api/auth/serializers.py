"""Формы запросов и ответов.

Сериализаторы ответов существуют не ради валидации, а ради контракта: из них
drf-spectacular строит схему, а из схемы генерируются типы фронтенда. Без них
типы выходят пустыми, и расхождение фронта с бэком перестаёт ловиться.
"""

from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)


class PageSerializer(serializers.Serializer):
    """Страница в меню. Префиксы API наружу не отдаются — это деталь защиты."""

    key = serializers.CharField()
    label = serializers.CharField()
    group = serializers.CharField(allow_blank=True)
    route = serializers.CharField()


class ProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    # Должность, а если её не заполнили — «Полный доступ» / «Сотрудник».
    title = serializers.CharField()
    is_superuser = serializers.BooleanField()
    pages = PageSerializer(many=True)


class CsrfSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
