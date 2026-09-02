"""Контракты раздела «Сроки оплаты»."""

from api.deadlines.serializers.deadlines import (
    DeadlineDetailSerializer,
    DeadlinesQuerySerializer,
    DeadlinesSerializer,
)

__all__ = [
    "DeadlineDetailSerializer",
    "DeadlinesQuerySerializer",
    "DeadlinesSerializer",
]
