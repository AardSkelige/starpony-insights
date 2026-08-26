from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.auth import services
from api.auth.serializers import LoginSerializer


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Выдать CSRF-куку перед формой входа.

    Фронтенд — статика, отданная прокси, шаблонов Django он не рендерит,
    поэтому получить токен из скрытого поля формы неоткуда.
    """
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    form = LoginSerializer(data=request.data)
    form.is_valid(raise_exception=True)

    user = services.sign_in(request, **form.validated_data)
    if user is None:
        # Одинаковый ответ на «нет такого пользователя» и «неверный пароль»:
        # разные тексты позволяют перебором узнать, кто в системе есть.
        return Response({"detail": "Неверный логин или пароль"}, status=status.HTTP_401_UNAUTHORIZED)

    return Response(services.profile(user))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    services.sign_out(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(services.profile(request.user))
