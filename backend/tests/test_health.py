import pytest


@pytest.mark.django_db
def test_healthz_checks_database(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_healthz_is_public(client):
    """Мониторинг ходит без сессии — иначе он проверяет форму входа, а не систему."""
    assert client.get("/healthz").status_code in (200, 503)


@pytest.mark.django_db
def test_healthz_answers_internal_host(client):
    """Проверка здоровья ходит с Host: 127.0.0.1 — она обязана проходить.

    Django с DEBUG=False отвечает 400 на незнакомый заголовок Host. Контейнер
    тогда объявляется больным при полностью работающем приложении, а деплой
    откатывается по таймауту ожидания здоровья — что и случилось при первой
    выкатке.
    """
    response = client.get("/healthz", headers={"host": "127.0.0.1:8000"})
    assert response.status_code == 200, "Проверка здоровья изнутри контейнера должна проходить"
