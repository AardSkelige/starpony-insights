from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.auth import services, throttling
from api.auth.serializers import (
    CsrfSerializer,
    DetailSerializer,
    LoginSerializer,
    ProfileSerializer,
)


@extend_schema(responses=CsrfSerializer)
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Выдать CSRF-куку перед формой входа.

    Фронтенд — статика, отданная прокси, шаблонов Django он не рендерит,
    поэтому получить токен из скрытого поля формы неоткуда.
    """
    return Response({"csrfToken": get_token(request)})


@extend_schema(
    request=LoginSerializer,
    responses={
        200: ProfileSerializer,
        401: DetailSerializer,
        429: DetailSerializer,
    },
)
@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    form = LoginSerializer(data=request.data)
    form.is_valid(raise_exception=True)

    username = form.validated_data["username"]

    # Проверка идёт до `authenticate()`: заблокированному не нужно даже
    # сверять пароль, а сверка — самая дорогая часть запроса (хеширование).
    attempt = throttling.check(request, username)
    if attempt.blocked:
        response = Response(
            {"detail": "Слишком много неудачных попыток. Повторите через 15 минут."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
        response["Retry-After"] = str(attempt.retry_after_seconds)
        return response

    user = services.sign_in(request, **form.validated_data)
    if user is None:
        throttling.record_failure(request, username)
        # Одинаковый ответ на «нет такого пользователя» и «неверный пароль»:
        # разные тексты позволяют перебором узнать, кто в системе есть.
        return Response({"detail": "Неверный логин или пароль"}, status=status.HTTP_401_UNAUTHORIZED)

    throttling.reset(request, username)
    return Response(services.profile(user))


@extend_schema(request=None, responses={204: None})
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    services.sign_out(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(responses=ProfileSerializer)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(services.profile(request.user))
