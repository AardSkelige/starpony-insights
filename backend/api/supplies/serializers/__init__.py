"""Контракты раздела приёмок."""

from api.supplies.serializers.materials import (
    SupplyMaterialDetailSerializer,
    SupplyMaterialsQuerySerializer,
    SupplyMaterialsSerializer,
)

__all__ = [
    "SupplyMaterialDetailSerializer",
    "SupplyMaterialsQuerySerializer",
    "SupplyMaterialsSerializer",
]
