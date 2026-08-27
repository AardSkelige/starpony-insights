"""View тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет."""

from django.http import FileResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from rest_framework import status

from api.shipments.serializers import (
    ShipmentProductDetailSerializer,
    ShipmentProductsQuerySerializer,
    ShipmentProductsSerializer,
)
from api.shipments.services import excel, product_detail, products
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="shipment_products_list",
    parameters=[ShipmentProductsQuerySerializer],
    responses=ShipmentProductsSerializer,
    summary="Товары в отгрузках",
    description="Что и сколько продано за период, свёрнутое по товару.",
)
@api_view(["GET"])
def shipment_products(request):
    query = ShipmentProductsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = products.Filters(**query.validated_data)

    payload = {
        **products.page(filters),
        "synced_at": documents_synced_at(),
        "channels": products.channels(filters),
    }
    return Response(ShipmentProductsSerializer(payload).data)


@extend_schema(
    operation_id="shipment_product_detail",
    parameters=[ShipmentProductsQuerySerializer],
    responses={200: ShipmentProductDetailSerializer, 404: None},
    summary="Товар в отгрузках — детали строки",
    description=(
        "Разбивка по каналам, последние отгрузки и остаток. Фильтры те же, "
        "что у таблицы: детали обязаны сходиться с числами своей строки."
    ),
)
@api_view(["GET"])
def shipment_product_detail(request, product_id: int):
    query = ShipmentProductsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = products.Filters(**query.validated_data)
    try:
        payload = product_detail.detail(filters, product_id)
    except product_detail.ProductNotSold:
        # 404, а не пустой ответ: строки с таким товаром в выборке нет,
        # и пустые блоки читались бы как «продаж не было», хотя запрос
        # просто не про эту выборку.
        return Response(
            {"detail": "Товар не встречается в этой выборке"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(ShipmentProductDetailSerializer(payload).data)


# Тип задаётся явно: FileResponse угадывает его по имени файла, а поток
# в памяти имени не имеет — и книга уезжает как application/octet-stream,
# который Excel открывать отказывается.
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@extend_schema(
    operation_id="shipment_products_xlsx",
    parameters=[ShipmentProductsQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Товары в отгрузках — выгрузка в Excel",
    description="Та же выборка, что на экране, но целиком: все страницы, а не видимая.",
)
@api_view(["GET"])
def shipment_products_xlsx(request):
    query = ShipmentProductsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = products.Filters(**query.validated_data)
    stream = excel.build(filters)

    name = _file_name(filters)
    return FileResponse(stream, as_attachment=True, filename=name, content_type=XLSX)


def _file_name(filters: products.Filters) -> str:
    """Имя файла говорит, что внутри и когда снято.

    Одной даты выгрузки мало: две выборки за разные периоды, скачанные
    в один день, получили бы одинаковое имя. Поэтому в имени — период данных,
    а дата выгрузки идёт следом.
    """
    if filters.date_from and filters.date_to:
        period = f"{filters.date_from:%d.%m.%Y}—{filters.date_to:%d.%m.%Y}"
    elif filters.date_from:
        period = f"с {filters.date_from:%d.%m.%Y}"
    elif filters.date_to:
        period = f"по {filters.date_to:%d.%m.%Y}"
    else:
        period = "весь период"

    return f"Товары в отгрузках, {period} (выгружено {timezone.localdate():%d.%m.%Y}).xlsx"
