"""View страницы «Материалы в приёмках».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.common.export import XLSX, export_name
from api.supplies.serializers import (
    SupplyMaterialDetailSerializer,
    SupplyMaterialsQuerySerializer,
    SupplyMaterialsSerializer,
)
from api.supplies.services import excel, material_detail, materials, selection
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="supply_materials_list",
    parameters=[SupplyMaterialsQuerySerializer],
    responses=SupplyMaterialsSerializer,
    summary="Материалы в приёмках",
    description=(
        "Что и почём закупали за период: количества, суммы, средняя цена, "
        "последняя цена и её изменение к предыдущей закупке."
    ),
)
@api_view(["GET"])
def supply_materials(request):
    query = SupplyMaterialsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = materials.Filters(**query.validated_data)

    payload = {
        **materials.page(filters),
        "synced_at": documents_synced_at(),
        "suppliers": selection.suppliers(
            date_from=filters.date_from, date_to=filters.date_to
        ),
    }
    return Response(SupplyMaterialsSerializer(payload).data)


@extend_schema(
    operation_id="supply_material_detail",
    parameters=[SupplyMaterialsQuerySerializer],
    responses={200: SupplyMaterialDetailSerializer, 404: None},
    summary="Материал в приёмках — откуда взялось число",
    description=(
        "История закупок и сравнение поставщиков. Фильтры те же, что "
        "у таблицы: слагаемые обязаны сходиться с числом своей строки."
    ),
)
@api_view(["GET"])
def supply_material_detail(request, material_id: int):
    query = SupplyMaterialsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = materials.Filters(**query.validated_data)
    try:
        payload = material_detail.detail(filters, material_id)
    except material_detail.MaterialNotPurchased:
        # 404, а не пустой ответ: материала в этой выборке нет, и пустые
        # блоки читались бы как «не закупался никогда», хотя запрос просто
        # не про эту выборку.
        return Response(
            {"detail": "Материал не закупался в этой выборке"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(SupplyMaterialDetailSerializer(payload).data)


@extend_schema(
    operation_id="supply_materials_xlsx",
    parameters=[SupplyMaterialsQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Материалы в приёмках — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — каждая "
        "закупка отдельной строкой."
    ),
)
@api_view(["GET"])
def supply_materials_xlsx(request):
    query = SupplyMaterialsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = materials.Filters(**query.validated_data)
    stream = excel.build(filters)

    name = export_name("Материалы в приёмках", filters.date_from, filters.date_to)
    return FileResponse(stream, as_attachment=True, filename=name, content_type=XLSX)
