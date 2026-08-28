"""View раздела отгрузок.

Пакетом, а не файлом: у каждой страницы три ручки — список, детали строки
и выгрузка, — и в одном файле они складываются в три сотни строк,
где правка одной страницы заставляет пролистать другую.
"""

from api.shipments.views.materials import (
    shipment_material_detail,
    shipment_materials,
    shipment_materials_xlsx,
)
from api.shipments.views.products import (
    shipment_product_detail,
    shipment_products,
    shipment_products_xlsx,
)

__all__ = [
    "shipment_material_detail",
    "shipment_materials",
    "shipment_materials_xlsx",
    "shipment_product_detail",
    "shipment_products",
    "shipment_products_xlsx",
]
