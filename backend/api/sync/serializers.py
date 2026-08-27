"""Контракт кнопки «Обновить»."""

from rest_framework import serializers


class SyncRunSerializer(serializers.Serializer):
    status = serializers.CharField()
    status_label = serializers.CharField()
    started_at = serializers.DateTimeField()
    finished_at = serializers.DateTimeField(allow_null=True)
    duration_seconds = serializers.FloatField(allow_null=True)
    # Сколько запросов ушло в МойСклад. Корзина общая с ботом, и рост этого
    # числа — первый признак, что синхронизация начала мешать чужой работе.
    request_count = serializers.IntegerField()
    error = serializers.CharField(allow_blank=True)


class SyncStatusSerializer(serializers.Serializer):
    running = serializers.BooleanField()
    started_at = serializers.DateTimeField(allow_null=True)


class RefusedSerializer(serializers.Serializer):
    detail = serializers.CharField()
    retry_after_seconds = serializers.IntegerField()
