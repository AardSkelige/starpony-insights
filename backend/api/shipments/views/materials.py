"""View страницы «Материалы в отгрузках».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.shipments.serializers import (
    ShipmentMaterialDetailSerializer,
    ShipmentMaterialsQuerySerializer,
    ShipmentMaterialsSerializer,
)
from api.shipments.services import excel_materials, material_detail, materials, selection
from api.shipments.views.common import XLSX, export_name
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="shipment_materials_list",
    parameters=[ShipmentMaterialsQuerySerializer],
    responses=ShipmentMaterialsSerializer,
    summary="Материалы в отгрузках",
    description=(
        "Сколько сырья ушло вместе с проданной продукцией. Проданное "
        "разворачивается по техкартам до того, что закупают."
    ),
)
@api_view(["GET"])
def shipment_materials(request):
    query = ShipmentMaterialsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = materials.Filters(**query.validated_data)

    payload = {
        **materials.page(filters),
        "synced_at": documents_synced_at(),
        "channels": selection.channels(
            date_from=filters.date_from, date_to=filters.date_to
        ),
    }
    return Response(ShipmentMaterialsSerializer(payload).data)


@extend_schema(
    operation_id="shipment_material_detail",
    parameters=[ShipmentMaterialsQuerySerializer],
    responses={200: ShipmentMaterialDetailSerializer, 404: None},
    summary="Материал в отгрузках — откуда взялось число",
    description=(
        "Из каких изделий материал пришёл и какими путями по техкартам. "
        "Фильтры те же, что у таблицы: слагаемые обязаны сходиться "
        "с числом своей строки."
    ),
)
@api_view(["GET"])
def shipment_material_detail(request, material_id: int):
    query = ShipmentMaterialsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = materials.Filters(**query.validated_data)
    try:
        payload = material_detail.detail(filters, material_id)
    except material_detail.MaterialNotUsed:
        # 404, а не пустой ответ: материала в этой выборке нет, и пустые
        # блоки читались бы как «не расходовался», хотя запрос просто
        # не про эту выборку.
        return Response(
            {"detail": "Материал не участвует в этой выборке"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(ShipmentMaterialDetailSerializer(payload).data)


@extend_schema(
    operation_id="shipment_materials_xlsx",
    parameters=[ShipmentMaterialsQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Материалы в отгрузках — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — проданное "
        "без техкарты: в сумму сырья оно не входит."
    ),
)
@api_view(["GET"])
def shipment_materials_xlsx(request):
    query = ShipmentMaterialsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = materials.Filters(**query.validated_data)
    stream = excel_materials.build(filters)

    name = export_name("Материалы в отгрузках", filters.date_from, filters.date_to)
    return FileResponse(stream, as_attachment=True, filename=name, content_type=XLSX)
