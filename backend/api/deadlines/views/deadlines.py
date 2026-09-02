"""View страницы «Сроки оплаты».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.common.export import XLSX, export_name
from api.deadlines.serializers import (
    DeadlineDetailSerializer,
    DeadlinesQuerySerializer,
    DeadlinesSerializer,
)
from api.deadlines.services import deadlines as service, detail, excel
from core.services.freshness import documents_synced_at


@extend_schema(
    operation_id="deadlines_list",
    parameters=[DeadlinesQuerySerializer],
    responses=DeadlinesSerializer,
    summary="Сроки оплаты",
    description=(
        "Кто должен, сколько и как давно. Три суммы отдельно: дебиторка, "
        "расчёты через площадку и товар, отгруженный по договору комиссии — "
        "складывать их нельзя, «нам должны» означает только первую."
    ),
)
@api_view(["GET"])
def deadlines(request):
    query = DeadlinesQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = service.Filters(**query.validated_data)

    payload = {**service.page(filters), "synced_at": documents_synced_at()}
    return Response(DeadlinesSerializer(payload).data)


@extend_schema(
    operation_id="deadlines_detail",
    responses={200: DeadlineDetailSerializer, 404: None},
    summary="Долг контрагента — из чего сложился",
    description=(
        "Неоплаченные документы контрагента с возрастом и сроком оплаты, "
        "плюс товар, отгруженный ему по договору комиссии."
    ),
)
@api_view(["GET"])
def deadline_detail(request, agent_id: int):
    payload = detail.of(agent_id)
    if payload is None:
        return Response(status=status.HTTP_404_NOT_FOUND)
    return Response(DeadlineDetailSerializer(payload).data)


@extend_schema(
    operation_id="deadlines_xlsx",
    parameters=[DeadlinesQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Сроки оплаты — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — каждый "
        "неоплаченный документ отдельной строкой."
    ),
)
@api_view(["GET"])
def deadlines_xlsx(request):
    query = DeadlinesQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = service.Filters(**query.validated_data)

    return FileResponse(
        excel.build(filters),
        as_attachment=True,
        # Периода у страницы нет — зато есть поиск, и он тоже сужает файл.
        # Без него в имени две выгрузки одного дня, полная и найденная,
        # назывались бы одинаково: ровно то столкновение, ради которого
        # `export_name` вообще держит середину имени.
        filename=export_name(_title(filters), None, None),
        content_type=XLSX,
    )


def _title(filters: service.Filters) -> str:
    """Заголовок файла. Поиск попадает в имя, потому что сужает содержимое."""
    if filters.search:
        return f"Сроки оплаты — {filters.search.strip()}"
    return "Сроки оплаты"
