"""View страницы «Каналы продаж».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.channels.serializers import ChannelsQuerySerializer, ChannelsSerializer
from api.channels.services import channels as service, excel
from api.common.export import XLSX, export_name
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="channels_list",
    parameters=[ChannelsQuerySerializer],
    responses=ChannelsSerializer,
    summary="Каналы продаж",
    description=(
        "Где продаём и сколько это приносит: выручка и её доля, число "
        "отгрузок, средний чек с разбросом, покупатели и ассортимент "
        "канала, а также выручка по каналам во времени."
    ),
)
@api_view(["GET"])
def channels(request):
    query = ChannelsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = service.Filters(**query.validated_data)

    payload = {**service.page(filters), "synced_at": documents_synced_at()}
    return Response(ChannelsSerializer(payload).data)


@extend_schema(
    operation_id="channels_xlsx",
    parameters=[ChannelsQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Каналы продаж — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — каждая "
        "отгрузка отдельной строкой."
    ),
)
@api_view(["GET"])
def channels_xlsx(request):
    query = ChannelsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = service.Filters(**query.validated_data)
    stream = excel.build(filters)

    name = export_name("Каналы продаж", filters.date_from, filters.date_to)
    return FileResponse(stream, as_attachment=True, filename=name, content_type=XLSX)
