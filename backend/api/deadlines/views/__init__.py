"""View раздела «Сроки оплаты»."""

from api.deadlines.views.deadlines import (
    deadline_detail,
    deadlines,
    deadlines_xlsx,
)

__all__ = [
    "deadline_detail",
    "deadlines",
    "deadlines_xlsx",
]
