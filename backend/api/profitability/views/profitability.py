"""View страницы «Прибыльность».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.common.export import XLSX, export_name
from api.profitability.serializers import (
    ProfitabilityQuerySerializer,
    ProfitabilitySerializer,
)
from api.profitability.services import excel, profitability as service
from api.profitability.services.selection import Basis, Filters
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="profitability_list",
    parameters=[ProfitabilityQuerySerializer],
    responses=ProfitabilitySerializer,
    summary="Прибыльность",
    description=(
        "На чём зарабатываем и на чём теряем: выручка, себестоимость "
        "на момент продажи, прибыль и маржа по каждому товару. Отдельно — "
        "маржа через площадки, у которой не вычтена их комиссия, товар "
        "на реализации и то, что отдано даром."
    ),
)
@api_view(["GET"])
def profitability(request):
    query = ProfitabilityQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = Filters(**query.validated_data)

    payload = {**service.page(filters), "synced_at": documents_synced_at()}
    return Response(ProfitabilitySerializer(payload).data)


@extend_schema(
    operation_id="profitability_xlsx",
    parameters=[ProfitabilityQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Прибыльность — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — линейки "
        "продукции: вопрос «на какой линейке зарабатываем» решается "
        "по группам, а не по товарам."
    ),
)
@api_view(["GET"])
def profitability_xlsx(request):
    query = ProfitabilityQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = Filters(**query.validated_data)
    stream = excel.build(filters)

    # База расчёта попадает в имя файла: два файла за один период иначе
    # выглядят одинаково и расходятся на 281 126 ₽.
    label = "Прибыльность" if filters.basis == Basis.SOLD else "Прибыльность (отгружено)"
    name = export_name(label, filters.date_from, filters.date_to)
    return FileResponse(stream, as_attachment=True, filename=name, content_type=XLSX)
