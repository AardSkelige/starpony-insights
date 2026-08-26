import pytest


@pytest.mark.django_db
def test_healthz_checks_database(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_healthz_is_public(client):
    """Мониторинг ходит без сессии — иначе он проверяет форму входа, а не систему."""
    assert client.get("/healthz").status_code in (200, 503)
