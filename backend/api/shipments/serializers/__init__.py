"""Контракты раздела отгрузок.

Пакетом, а не файлом: у двух страниц свои наборы полей, и в одном файле
они складывались бы в три сотни строк, где правка одной страницы заставляет
пролистать другую.
"""

from api.shipments.serializers.common import ShipmentQuerySerializer
from api.shipments.serializers.materials import (
    ShipmentMaterialDetailSerializer,
    ShipmentMaterialsQuerySerializer,
    ShipmentMaterialsSerializer,
)
from api.shipments.serializers.products import (
    ShipmentProductDetailSerializer,
    ShipmentProductsQuerySerializer,
    ShipmentProductsSerializer,
)

__all__ = [
    "ShipmentQuerySerializer",
    "ShipmentMaterialDetailSerializer",
    "ShipmentMaterialsQuerySerializer",
    "ShipmentMaterialsSerializer",
    "ShipmentProductDetailSerializer",
    "ShipmentProductsQuerySerializer",
    "ShipmentProductsSerializer",
]
