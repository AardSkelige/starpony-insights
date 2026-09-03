"""Выдача доступов в админке.

**Умолчание — запрет**, и это делает ошибку выдачи тихой в обе стороны.
Опечатка в ключе создаёт доступ в никуда: строка в таблице есть, страницы
у человека нет, и признака этому не существует. Забытая выдача даёт вход
в пустое приложение — человек видит оболочку без единого пункта меню
и приходит с вопросом, на который в базе ответа не найти.

Поэтому проверяется не «сохранилось ли», а то, чем ошибиться нельзя:
список страниц берётся из реестра, кто выдал — из входа в админку,
а «ни одной» видно из списка пользователей.
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.admin import UserAdmin

from api.access import PAGES
from core.admin import UserAccessForm, UserAdminWithAccess
from core.models import User, UserPageAccess

pytestmark = pytest.mark.django_db


@pytest.fixture
def site():
    return UserAdminWithAccess(User, AdminSite())


class FakeRequest:
    """Ровно то, чем пользуется действие админки: кто его запустил."""

    def __init__(self, user):
        self.user = user

    def _messages(self):  # pragma: no cover — сообщения здесь не проверяются
        return []


@pytest.fixture
def request_of():
    def _make(user):
        request = FakeRequest(user)
        # `message_user` пишет в очередь сообщений; в тесте она не нужна,
        # но без заглушки падает на отсутствии middleware.
        request._messages = _Sink()
        return request

    return _make


class _Sink:
    def add(self, *args, **kwargs):
        return None


class TestCheckboxesComeFromRegistry:
    """Разделы отмечаются галочками: список весь на виду и берётся из реестра.

    Пока страница набиралась строкой, опечатка в `shipments-products`
    создавала доступ в никуда — строка в таблице есть, страницы у человека
    нет, и признака этому не существует.
    """

    def test_список_совпадает_с_реестром(self):
        keys = [key for key, _ in UserAccessForm().fields["pages"].choices]

        assert keys == [page.key for page in PAGES]

    def test_подпись_несёт_и_название_и_ключ(self):
        """Ключ виден рядом: он же лежит в базе, и разбирать выданное по нему."""
        labels = dict(UserAccessForm().fields["pages"].choices)

        assert labels["shipments-products"] == "Товары в отгрузках · shipments-products"

    def test_ключа_вне_реестра_выбрать_нельзя(self):
        form = UserAccessForm(data={"username": "кто-то", "pages": ["shipment-products"]})

        assert not form.is_valid()
        assert "pages" in form.errors

    def test_отмечено_то_что_выдано(self, make_user):
        user = make_user("сотрудник", pages=("suppliers", "channels"))

        form = UserAccessForm(instance=user)

        assert set(form.fields["pages"].initial) == {"suppliers", "channels"}


class TestGrantAll:
    """Обычный случай — «всё, кроме пары разделов»: выдать всё и снять лишнее."""

    def test_выдаёт_все_страницы(self, site, make_user, request_of):
        user = make_user("новичок")
        admin = make_user("админ", superuser=True)

        site.grant_all_pages(request_of(admin), User.objects.filter(pk=user.pk))

        assert set(user.page_access.values_list("page_key", flat=True)) == {
            page.key for page in PAGES
        }

    def test_повторная_выдача_не_двоит(self, site, make_user, request_of):
        user = make_user("новичок", pages=("suppliers",))
        admin = make_user("админ", superuser=True)
        request = request_of(admin)

        site.grant_all_pages(request, User.objects.filter(pk=user.pk))
        site.grant_all_pages(request, User.objects.filter(pk=user.pk))

        assert user.page_access.count() == len(PAGES)

    def test_кто_выдал_берётся_из_входа_в_админку(
        self, site, make_user, request_of
    ):
        """Поле, которое надо выбрать из списка всех людей, заполняют наугад."""
        user = make_user("новичок")
        admin = make_user("админ", superuser=True)

        site.grant_all_pages(request_of(admin), User.objects.filter(pk=user.pk))

        assert set(user.page_access.values_list("granted_by__username", flat=True)) == {
            "админ"
        }


class TestRevokeAll:
    def test_снимает_все(self, site, make_user, request_of):
        user = make_user("бывший", pages=("suppliers", "channels"))
        admin = make_user("админ", superuser=True)

        site.revoke_all_pages(request_of(admin), User.objects.filter(pk=user.pk))

        assert user.page_access.count() == 0

    def test_чужие_доступы_не_трогает(self, site, make_user, request_of):
        keep = make_user("остался", pages=("suppliers",))
        drop = make_user("бывший", pages=("suppliers",))
        admin = make_user("админ", superuser=True)

        site.revoke_all_pages(request_of(admin), User.objects.filter(pk=drop.pk))

        assert keep.page_access.count() == 1


class TestSummaryInTheList:
    """«Завёл человека, а у него пусто» обязано выясняться отсюда, а не от него."""

    def test_без_доступов_говорит_прямо(self, site, make_user):
        assert "ни одного" in site.granted_pages(make_user("новичок"))

    def test_суперпользователю_доступы_не_нужны(self, site, make_user):
        assert site.granted_pages(make_user("бог", superuser=True)) == (
            "все (суперпользователь)"
        )

    def test_показывает_названия_а_не_ключи(self, site, make_user):
        summary = site.granted_pages(make_user("сотрудник", pages=("suppliers",)))

        assert summary == "1: Поставщики"

    def test_ключ_вне_реестра_назван_вслух(self, site, make_user):
        """Страницу могли убрать из кода, а строка осталась.

        Молча показать сам ключ значило бы выдать мёртвый доступ за живой.
        """
        user = make_user("сотрудник")
        UserPageAccess.objects.create(user=user, page_key="старая-страница")

        assert "нет в реестре" in site.granted_pages(user)


class TestFormPutsAccessInSight:
    """«Не видно ничего» — это про форму, а не про права.

    Инлайн доступов Django рисует после всех наборов полей. Пока группы
    и права Django стояли развёрнутыми, форма занимала два экрана, а нужное
    оказывалось под ними — и выдавать доступы шли не туда.
    """

    def test_группы_и_права_django_свёрнуты(self, site):
        collapsed = {
            title
            for title, options in site.fieldsets
            if "collapse" in options.get("classes", ())
        }

        assert "Группы и права Django" in collapsed

    def test_разделы_стоят_выше_прав_django(self, site):
        """Порядок наборов полей и есть ответ на «где это».

        Пока разделы шли после групп и прав Django, форма занимала два
        экрана, и выдавать доступы шли не туда.
        """
        titles = [title for title, _ in site.fieldsets]

        assert titles.index("Разделы") < titles.index("Группы и права Django")

    def test_ни_одно_поле_не_потеряно(self, site):
        """Переписанные наборы полей легко теряют поле, и молча."""
        shown = {
            field
            for _, options in site.fieldsets
            for field in options["fields"]
        }
        assert "pages" in shown
        expected = {
            field
            for _, options in UserAdmin.fieldsets
            for field in options["fields"]
        }

        assert expected <= shown


class TestSidebarTitle:
    """Подпись под именем в меню: должность важнее прав.

    «Полный доступ» — ответ на вопрос, которого человек про себя не задаёт.
    Правило живёт на сервере, а не на фронтенде: два места решали бы его
    по-своему и разошлись бы.
    """

    def test_должность_побеждает_права(self, make_user):
        user = make_user("бог", superuser=True)
        user.title = "Хранитель остатков"
        user.save(update_fields=["title"])

        assert user.sidebar_title == "Хранитель остатков"

    def test_без_должности_остаются_права(self, make_user):
        assert make_user("сотрудник").sidebar_title == "Сотрудник"
        assert make_user("бог", superuser=True).sidebar_title == "Полный доступ"

    def test_должность_едет_в_профиль(self, make_user):
        from api.auth.services import profile

        user = make_user("сотрудник")
        user.title = "Повелитель ДЭТА"
        user.save(update_fields=["title"])

        assert profile(user)["title"] == "Повелитель ДЭТА"

    def test_должность_правится_в_админке(self, site):
        fields = {
            field
            for _, options in site.fieldsets
            for field in options["fields"]
        }

        assert "title" in fields


def test_пароль_остаётся_нередактируемым(site):
    """Хеш в обычном поле ввода — это пароль, которым потом не войти.

    Форма пользователя переписывалась ради галочек разделов, и голая
    `ModelForm` показала бы `password` обычным текстовым полем вместе
    со ссылкой «Сбросить пароль», которая при этом пропадает.
    """
    from django.contrib.auth.forms import ReadOnlyPasswordHashField

    field = site.form.base_fields["password"]

    assert isinstance(field, ReadOnlyPasswordHashField)
