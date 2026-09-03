"""View «Расчёта производства». Тонкие: разобрать → позвать сервис → отдать.

Два запроса на два звена цепочки. Верхний — что кончается — зависит только
от периода и горизонта; нижний — что закупить — только от состава партии.
Слей их в один, и правка количества в одной строке перезапрашивала бы весь
каталог вместе с продажами за полгода.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.production.serializers import (
    BatchQuerySerializer,
    BatchSerializer,
    ProductsQuerySerializer,
    ProductsSerializer,
)
from api.production.services import payload as batch_service
from api.production.services import products as products_service
from api.production.services.selection import Filters, parse_batch
from core.services.freshness import documents_synced_at, oldest_of, stock_synced_at


@extend_schema(
    operation_id="production_products",
    parameters=[ProductsQuerySerializer],
    responses=ProductsSerializer,
    summary="Что кончается и сколько этого произвести",
    description=(
        "Товары с артикулом: свободный остаток против темпа продаж за период. "
        "Отвечает на вопрос, которого в учёте нет, — «много это или мало»: "
        "двенадцать репеллентов выглядят запасом, пока не выяснится, что их "
        "берут по четыре в день. Рядом с каждым — сколько произвести, чтобы "
        "хватило на выбранный горизонт."
    ),
)
@api_view(["GET"])
def products(request):
    query = ProductsQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    filters = Filters(**query.validated_data)
    payload = {**products_service.page(filters), "synced_at": _synced_at()}
    return Response(ProductsSerializer(payload).data)


@extend_schema(
    operation_id="production_batch",
    parameters=[BatchQuerySerializer],
    responses=BatchSerializer,
    summary="Что закупить под партию",
    description=(
        "Состав партии передаётся повторяющимся `item` в виде "
        "«артикул:количество». Товары разворачиваются по техкартам до сырья "
        "рекурсивно — производство идёт в два шага, и прямой состав показал "
        "бы полуфабрикат, которого не закупают. Нехватка считается от "
        "свободного остатка; неснижаемый остаток идёт вторым сигналом. "
        "Строка, не попавшая в расчёт, возвращается названной, а не "
        "выбрасывается молча."
    ),
)
@api_view(["GET"])
def batch(request):
    query = BatchQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)

    picked = query.validated_data.pop("item")
    # Период и горизонт нужны здесь по той же причине, что и в списке
    # товаров: позиция без количества означает «посчитай сам», а считается
    # предложение из продаж за период и выбранного срока.
    filters = Filters(**query.validated_data)

    # Разбор в два приёма: сериализатор стережёт длину каждой строки
    # и попадает в схему, `parse_batch` — форму «артикул[:количество]»
    # и потолок числа позиций. Второе сериализатором не выражается:
    # повторы одного артикула надо сложить, а не оставить рядом.
    payload = {
        **batch_service.page(parse_batch(picked), filters),
        "synced_at": _synced_at(),
    }
    return Response(BatchSerializer(payload).data)


def _synced_at():
    """Свежесть страницы — по самому отставшему из двух источников.

    Продажи берутся из документов (ночной прогон), остатки — из отчёта
    (каждые 10–15 минут). Показать только время документов значило бы
    назвать страницу вчерашней, когда остатки свежие; только время
    остатков — пообещать свежесть продажам, которых у нас нет.

    Разница не умозрительная: 03.09 остатки в зеркале отставали на неделю,
    и все семнадцать кончившихся товаров выглядели как «остатка в отчёте
    нет вовсе».
    """
    return oldest_of(documents_synced_at(), stock_synced_at())
