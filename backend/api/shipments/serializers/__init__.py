"""Контракты раздела отгрузок.

Пакетом, а не файлом: у двух страниц свои наборы полей, и в одном файле
они складывались бы в три сотни строк, где правка одной страницы заставляет
пролистать другую.
"""

from api.shipments.serializers.common import (
    SalesChannelSerializer,
    SelectionQuerySerializer,
)
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
    "SalesChannelSerializer",
    "SelectionQuerySerializer",
    "ShipmentMaterialDetailSerializer",
    "ShipmentMaterialsQuerySerializer",
    "ShipmentMaterialsSerializer",
    "ShipmentProductDetailSerializer",
    "ShipmentProductsQuerySerializer",
    "ShipmentProductsSerializer",
]
