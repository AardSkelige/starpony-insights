"""View страницы «Инвентаризация».

Тонкий: разобрать фильтры → позвать сервис → отдать. Запросов к БД нет.
"""

from django.http import FileResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.common.export import XLSX, export_name
from api.inventory.serializers import InventoryQuerySerializer, InventorySerializer
from api.inventory.services import blocks, excel, selection
from api.inventory.services import inventory as service
from core.services.freshness import stock_synced_at


@extend_schema(
    operation_id="inventory_list",
    parameters=[InventoryQuerySerializer],
    responses=InventorySerializer,
    summary="Инвентаризация",
    description=(
        "Когда пересчитывали каждую позицию и на сколько она не сошлась. "
        "Расхождение в деньгах считается по себестоимости остатков: "
        "в документах учёта цена заполнена у меньшинства позиций."
    ),
)
@api_view(["GET"])
def inventory(request):
    query = InventoryQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = selection.Filters(**query.validated_data)
    whole = service.prepared(filters)
    rows = whole["rows"]

    payload = {
        **service.page(whole, filters),
        # Блоки считаются по всей выборке, а не по странице: свёрнутый блок
        # про то же множество, что таблица, и листание не должно его менять.
        "coverage": blocks.coverage(rows),
        "worst": blocks.worst(rows),
        "repeats": blocks.repeats(rows),
        "documents": {
            **blocks.documents(filters),
            # Когда каждый склад трогали последний раз — «когда считали
            # сырьё» спрашивают раньше, чем «какие были документы».
            "stores": blocks.store_recounts(filters),
        },
        "stores": selection.stores(),
        "folders": selection.folders(),
        # Свежесть — по остаткам: себестоимость, которой считаются деньги,
        # приезжает вместе с ними каждые пятнадцать минут, а сами
        # инвентаризации — ночным прогоном. Врать про более свежее нельзя.
        "synced_at": stock_synced_at(),
    }
    return Response(InventorySerializer(payload).data)


@extend_schema(
    operation_id="inventory_xlsx",
    parameters=[InventoryQuerySerializer],
    responses={(200, XLSX): OpenApiTypes.BINARY},
    summary="Инвентаризация — выгрузка в Excel",
    description=(
        "Та же выборка, что на экране, целиком. Вторым листом — сами "
        "инвентаризации: когда, на каком складе и сколько позиций разошлось."
    ),
)
@api_view(["GET"])
def inventory_xlsx(request):
    query = InventoryQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = selection.Filters(**query.validated_data)
    stream = excel.build(filters)

    return FileResponse(
        stream,
        as_attachment=True,
        filename=export_name("Инвентаризация", None, None),
        content_type=XLSX,
    )
