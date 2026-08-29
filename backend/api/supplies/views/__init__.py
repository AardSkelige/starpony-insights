"""View раздела приёмок."""

from api.supplies.views.materials import (
    supply_material_detail,
    supply_materials,
    supply_materials_xlsx,
)

__all__ = [
    "supply_material_detail",
    "supply_materials",
    "supply_materials_xlsx",
]
