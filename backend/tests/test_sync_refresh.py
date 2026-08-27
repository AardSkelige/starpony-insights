"""Кнопка «Обновить»: единственное место, где человек доходит до МойСклада.

Проверяется не сам проход — он покрыт своими тестами, — а ограничения,
которые не дают выбрать корзину лимита, общую с ботом Agent - StarPony.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone

from api.sync import services
from core.models import SyncKind, SyncRun, SyncStatus
from moysklad.sync.full import AlreadyRunning, TokenMissing

pytestmark = pytest.mark.django_db

URL = "/api/sync/refresh/"


def finished_run(minutes_ago: float, status=SyncStatus.SUCCESS) -> SyncRun:
    """Запись журнала в базе — как след прошлого прогона."""
    moment = timezone.now() - timedelta(minutes=minutes_ago)
    return SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS, status=status, started_at=moment, finished_at=moment
    )


def fake_result() -> SyncRun:
    """То, что вернул бы прогон, — но без записи в базу.

    Сохранять нельзя: запись легла бы в журнал раньше вызова и сама же
    заблокировала бы запуск паузой между прогонами.
    """
    moment = timezone.now()
    return SyncRun(
        kind=SyncKind.DOCUMENTS,
        status=SyncStatus.SUCCESS,
        started_at=moment,
        finished_at=moment,
    )


def test_refresh_runs_the_full_sync():
    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        services.refresh()

    sync.assert_called_once_with(manual=True)


def test_refresh_marks_the_run_as_manual():
    """Прогон по кнопке отличим от ночного: иначе не понять, кто съел лимит."""
    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        services.refresh()

    assert sync.call_args.kwargs["manual"] is True


def test_refresh_refuses_within_the_cooldown():
    """Пауза между запусками — защита общей с ботом корзины.

    Ночной проход тратит около двухсот запросов. Десять нажатий подряд
    съели бы корзину, из которой работает бот, и он получил бы 429.
    """
    finished_run(minutes_ago=1)

    with patch("api.sync.services.run_documents_sync") as sync:
        with pytest.raises(services.Refused) as refusal:
            services.refresh()

    sync.assert_not_called()
    assert refusal.value.retry_after_seconds > 0


def test_refresh_allows_after_the_cooldown():
    finished_run(minutes_ago=5)

    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        services.refresh()

    sync.assert_called_once()


def test_refresh_refuses_while_a_run_is_going():
    """Идущий прогон виден по статусу: блокировка живёт в другом соединении.

    Возраст выбран между двумя порогами: пауза между запусками уже прошла
    (иначе отказ дала бы она, и проверка статуса осталась бы не у дел),
    а срок годности ещё нет (иначе прогон считался бы брошенным).
    """
    SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS,
        status=SyncStatus.RUNNING,
        started_at=timezone.now() - timedelta(minutes=5),
    )

    with patch("api.sync.services.run_documents_sync") as sync:
        with pytest.raises(services.Refused):
            services.refresh()

    sync.assert_not_called()


def test_refresh_ignores_runs_of_another_kind():
    """Прогон остатков идёт каждые 15 минут и не должен блокировать кнопку."""
    SyncRun.objects.create(
        kind=SyncKind.STATE, status=SyncStatus.SUCCESS, started_at=timezone.now()
    )

    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        services.refresh()

    sync.assert_called_once()


def test_refresh_explains_a_missing_token():
    """«Токена нет» — это настройка, а не сбой сети: текст должен различаться."""
    with patch("api.sync.services.run_documents_sync", side_effect=TokenMissing()):
        with pytest.raises(services.Refused) as refusal:
            services.refresh()

    assert "токен" in refusal.value.reason.lower()


def test_refresh_survives_a_race_with_the_scheduled_run():
    """Крон мог начать прогон между проверкой и запуском.

    Блокировка это ловит, и человек должен увидеть объяснение, а не пятисотую.
    """
    with patch("api.sync.services.run_documents_sync", side_effect=AlreadyRunning()):
        with pytest.raises(services.Refused):
            services.refresh()


# --- Через HTTP ---------------------------------------------------------------


def test_endpoint_requires_login(client):
    assert client.post(URL).status_code == 401


def test_endpoint_is_open_to_any_signed_in_user(client, make_user):
    """Кнопка есть на каждой странице, поэтому доступна каждому вошедшему.

    Опасность здесь не в правах, а в частоте, и её сдерживает пауза.
    """
    client.force_login(make_user(pages=[]))

    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        response = client.post(URL)

    assert response.status_code == 200


def test_endpoint_answers_429_when_asked_too_often(client, make_user):
    """429, а не 400: фронт показывает по нему обратный отсчёт."""
    finished_run(minutes_ago=1)
    client.force_login(make_user(pages=[]))

    response = client.post(URL)

    assert response.status_code == 429
    assert response.json()["retry_after_seconds"] > 0


def test_endpoint_answers_409_when_a_run_is_going(client, make_user):
    """Отдельный код: «идёт прогон» — это не «слишком часто», отсчёта нет."""
    SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS,
        status=SyncStatus.RUNNING,
        started_at=timezone.now() - timedelta(minutes=5),
    )
    client.force_login(make_user(pages=[]))

    response = client.post(URL)

    assert response.status_code == 409


def test_endpoint_rejects_get(client, make_user):
    """Обновление меняет состояние, поэтому только POST.

    По GET его дёрнул бы любой предзагрузчик ссылок в браузере.
    """
    client.force_login(make_user(pages=[]))

    assert client.get(URL).status_code == 405


def test_endpoint_reports_what_happened(client, make_user):
    """В ответе — статус и расход запросов: по ним видно, не мешаем ли боту."""
    client.force_login(make_user(pages=[]))
    run = fake_result()
    run.request_count = 214

    with patch("api.sync.services.run_documents_sync", return_value=run):
        body = client.post(URL).json()

    assert body["status"] == SyncStatus.SUCCESS
    assert body["request_count"] == 214
    assert body["duration_seconds"] is not None


def test_abandoned_run_does_not_block_the_button_forever():
    """Брошенная запись «идёт» не должна выключать кнопку навсегда.

    Так бывает, когда процесс умер, не закрыв журнал: воркер убит по таймауту,
    контейнер перезапущен, машина перезагружена. Без срока годности одна такая
    запись держала бы отказ до следующего ночного прогона.
    """
    SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS,
        status=SyncStatus.RUNNING,
        started_at=timezone.now() - services.STALE_AFTER - timedelta(minutes=1),
    )

    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        services.refresh()

    sync.assert_called_once()


def test_abandoned_run_is_closed_in_the_journal():
    """Брошенная запись закрывается, а не остаётся «идущей» вечно.

    Иначе журнал утверждает, что прогон идёт до сих пор, и следующий отказ
    снова сошлётся на неё.
    """
    stale = SyncRun.objects.create(
        kind=SyncKind.DOCUMENTS,
        status=SyncStatus.RUNNING,
        started_at=timezone.now() - services.STALE_AFTER - timedelta(minutes=1),
    )

    with patch("api.sync.services.run_documents_sync") as sync:
        sync.return_value = fake_result()
        services.refresh()

    stale.refresh_from_db()
    assert stale.status == SyncStatus.FAILED
    assert stale.finished_at is not None
    assert stale.error


def test_cooldown_never_reports_zero_seconds_left():
    """Остаток паузы округляется вверх, а не в ноль.

    По нулю view отличает «слишком часто» от «сейчас нельзя по другой
    причине», и отказ уехал бы кодом 409 вместо 429.
    """
    finished_run(minutes_ago=services.COOLDOWN.total_seconds() / 60 - 0.005)

    with pytest.raises(services.Refused) as refusal:
        services.refresh()

    assert refusal.value.retry_after_seconds >= 1


def test_endpoint_sends_retry_after_header(client, make_user):
    """Стандартный заголовок: клиент понимает паузу, не разбирая тело."""
    finished_run(minutes_ago=1)
    client.force_login(make_user(pages=[]))

    response = client.post(URL)

    assert response["Retry-After"] == str(response.json()["retry_after_seconds"])
