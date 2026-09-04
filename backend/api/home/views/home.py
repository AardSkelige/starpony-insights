"""View главной.

Тонкий, как и остальные: позвать сборку → сериализовать → вернуть.
Своего здесь только одно — пользователь передаётся в сервис, потому что
состав ответа зависит от его доступов (`api/home/services/page.py`).
"""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from api.home.serializers import HomeSerializer
from api.home.services import page as service


@extend_schema(
    operation_id="home",
    responses=HomeSerializer,
    summary="Главная",
    description=(
        "Состояние дел за последний полный месяц: что требует решения, "
        "во что вложены деньги, как идут продажи и на чём мы зарабатываем. "
        "Состав ответа зависит от доступов: плитка раздела, закрытого "
        "для пользователя, приходит пустой."
    ),
)
@api_view(["GET"])
def home(request):
    return Response(HomeSerializer(service.build(request.user)).data)
