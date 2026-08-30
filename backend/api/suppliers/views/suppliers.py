"""View страницы «Поставщики».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.common.export import XLSX, export_name
from api.suppliers.serializers import SuppliersQuerySerializer, SuppliersSerializer
from api.suppliers.services import excel, suppliers as service
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="suppliers_list",
    parameters=[SuppliersQuerySerializer],
    responses=SuppliersSerializer,
    summary="Поставщики",
    description=(
        "Кто, на какие суммы и как часто поставляет: приёмки, наименования, "
        "регулярность поставок и срок от заказа до прихода товара."
    ),
)
@api_view(["GET"])
def suppliers(request):
    query = SuppliersQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = service.Filters(**query.validated_data)

    payload = {**service.page(filters), "synced_at": documents_synced_at()}
    return Response(SuppliersSerializer(payload).data)


@extend_schema(
    operation_id="suppliers_xlsx",
    parameters=[SuppliersQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Поставщики — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — каждая "
        "поставка отдельной строкой."
    ),
)
@api_view(["GET"])
def suppliers_xlsx(request):
    query = SuppliersQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = service.Filters(**query.validated_data)
    stream = excel.build(filters)

    name = export_name("Поставщики", filters.date_from, filters.date_to)
    return FileResponse(stream, as_attachment=True, filename=name, content_type=XLSX)
