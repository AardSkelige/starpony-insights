"""Поведение защиты, а не только её конфигурация."""

import pytest

from core.models import User


@pytest.mark.django_db
def test_anonymous_gets_401(client):
    response = client.get("/api/auth/me/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_login_and_me(client, make_user):
    make_user(username="anna", pages=["deadlines"])

    response = client.post(
        "/api/auth/login/",
        {"username": "anna", "password": "secret-pass-123"},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert [page["key"] for page in response.json()["pages"]] == ["deadlines"]

    assert client.get("/api/auth/me/").status_code == 200


@pytest.mark.django_db
def test_wrong_password_says_nothing_extra(client, make_user):
    make_user(username="anna")
    response = client.post(
        "/api/auth/login/",
        {"username": "anna", "password": "wrong"},
        content_type="application/json",
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"


@pytest.mark.django_db
def test_page_access_is_enforced(client, make_user):
    make_user(username="anna", pages=["deadlines"])
    client.login(username="anna", password="secret-pass-123")

    # Страница выдана — путь проходит защиту (дальше 404: view ещё не написан).
    assert client.get("/api/deadlines/").status_code != 403
    # Соседняя страница не выдана.
    assert client.get("/api/suppliers/").status_code == 403


@pytest.mark.django_db
def test_undeclared_path_is_denied(client, make_user):
    """Умолчание — запрет. Главное отличие от модели Horse Bio."""
    make_user(username="anna", pages=["deadlines"])
    client.login(username="anna", password="secret-pass-123")

    response = client.get("/api/something-nobody-declared/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_superuser_sees_everything(client):
    User.objects.create_superuser(username="root", password="secret-pass-123")
    client.login(username="root", password="secret-pass-123")

    assert client.get("/api/something-nobody-declared/").status_code != 403
    assert len(client.get("/api/auth/me/").json()["pages"]) > 0


@pytest.mark.django_db
def test_similar_prefixes_do_not_leak(client, make_user):
    """«/api/supplies/materials/» не должен открываться доступом к поставщикам."""
    make_user(username="anna", pages=["suppliers"])
    client.login(username="anna", password="secret-pass-123")

    assert client.get("/api/supplies/materials/").status_code == 403


@pytest.mark.django_db
def test_admin_shows_login_page_not_json(client):
    """Аноним на /admin/ должен получить форму входа, а не JSON.

    Раньше middleware перехватывал путь раньше Django и отдавал
    {"detail": "Требуется вход"} — в браузере это выглядело как поломка.
    """
    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


@pytest.mark.django_db
def test_admin_rejects_non_staff(client, make_user):
    """Обычный пользователь внутрь админки не попадает.

    Проверку делает сам Django, но убедиться в ней надо: мы сознательно
    сняли с этого пути собственную защиту.
    """
    make_user(username="anna", pages=["deadlines"])
    client.login(username="anna", password="secret-pass-123")

    response = client.get("/admin/")
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]
