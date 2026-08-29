"""Маршруты раздела приёмок. Только пути."""

from django.urls import path

from api.supplies import views

urlpatterns = [
    path("materials/", views.supply_materials, name="supply-materials"),
    path("materials/xlsx/", views.supply_materials_xlsx, name="supply-materials-xlsx"),
    path(
        "materials/<int:material_id>/",
        views.supply_material_detail,
        name="supply-material-detail",
    ),
]
