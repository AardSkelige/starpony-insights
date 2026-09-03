from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Group

from api.access import PAGES, PAGES_BY_KEY
from core.models import (
    BackupRun,
    SyncEntityResult,
    SyncRun,
    User,
    UserPageAccess,
    WritebackChange,
    WritebackRun,
    WritebackSwitch,
)


def page_choices() -> list[tuple[str, str]]:
    """Страницы для выпадающего списка — прямо из реестра `PAGES`.

    Список считается при отрисовке, а не при импорте: новая страница
    появляется здесь сама, без миграции и без второго перечня.

    Ключ показывается рядом с названием намеренно: он же лежит в базе,
    и без него разбирать выданное по строке таблицы нечем.
    """
    return [(page.key, f"{page.label} · {page.key}") for page in PAGES]


class UserAccessForm(UserChangeForm):
    """Разделы — галочками, все сразу, одним сохранением.

    Прежде это был список строк: чтобы выдать девять разделов, надо было
    девять раз нажать «добавить» и девять раз выбрать страницу. Обычный же
    случай — «всё, кроме пары разделов», и он требует видеть весь список
    целиком, с отметками, а не собирать его по одной.

    Поле не модельное: доступ живёт отдельными строками `UserPageAccess`,
    и это правильно — у каждой есть «кто выдал» и «когда». Форма только
    показывает их одним списком и сводит обратно при сохранении.
    """

    pages = forms.MultipleChoiceField(
        label="Разделы",
        choices=page_choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=(
            "Что человек увидит в меню. Снятая галочка закрывает и страницу, "
            "и её данные — проверка стоит на сервере, а не только в меню. "
            "Суперпользователю галочки не нужны: ему видно всё."
        ),
    )

    class Meta(UserChangeForm.Meta):
        # Наследуемся от формы Django, а не от голой `ModelForm`: у неё
        # пароль — поле только для чтения со ссылкой «Сбросить пароль».
        # Голая форма показывала бы хеш обычным полем ввода, и правка
        # в нём ставит пользователю пароль, которым не войти.
        model = User
        fields = "__all__"

    class Media:
        # Разметка списка галочек. Колонка поля в админке узкая, и десять
        # подписей переносились по три строки каждая.
        css = {"all": ("admin/css/page-access.css",)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["pages"].initial = list(
                self.instance.page_access.values_list("page_key", flat=True)
            )


@admin.register(User)
class UserAdminWithAccess(UserAdmin):
    """Пользователь вместе с выданными ему страницами.

    **Умолчание — запрет** (`api/access.py`), и это верно: ошибка
    забывчивости обязана закрывать доступ. Но тогда «завёл человека,
    а у него пусто» обязано быть видно отсюда, а не выясняться от него
    самого, — поэтому число выданных страниц стоит прямо в списке.
    """

    form = UserAccessForm
    list_display = (*UserAdmin.list_display, "title", "granted_pages")
    actions = ("grant_all_pages", "revoke_all_pages")

    # Django рисует наборы полей сверху вниз, и по умолчанию разделы
    # оказывались под двумя огромными списками — групп и прав Django,
    # которые в этом проекте не решают ничего. Форма на два экрана, нужное
    # в самом низу: ровно поэтому «завёл человека, а там не видно ничего».
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Персональная информация",
            {
                "fields": ("first_name", "last_name", "title", "email"),
                "description": "Должность видна человеку под его именем в меню.",
            },
        ),
        (
            "Разделы",
            {
                "fields": ("pages",),
                "description": "Отметьте, что человеку видно. Сохраняется вместе с формой.",
            },
        ),
        (
            "Вход",
            {"fields": ("is_active", "is_staff", "is_superuser")},
        ),
        ("Важные даты", {"fields": ("last_login", "date_joined")}),
        (
            "Группы и права Django",
            {
                "classes": ("collapse",),
                "fields": ("groups", "user_permissions"),
                "description": (
                    "В этом проекте не используются: доступ к разделам решает "
                    "реестр страниц выше, а не права Django."
                ),
            },
        ),
    )

    @admin.display(description="Разделы")
    def granted_pages(self, user: User) -> str:
        if user.is_superuser:
            return "все (суперпользователь)"

        keys = list(user.page_access.values_list("page_key", flat=True))
        if not keys:
            return "— ни одного, войдёт в пустое"

        names = [
            PAGES_BY_KEY[key].label if key in PAGES_BY_KEY else f"{key} (нет в реестре)"
            for key in keys
        ]
        return f"{len(names)}: " + ", ".join(names)

    def save_model(self, request, obj, form, change):
        """Свести галочки к строкам доступа.

        Уцелевшие строки не пересоздаются: у них есть «кто выдал» и «когда»,
        и снести их ради удобства значило бы стереть историю выдачи при каждом
        сохранении формы.
        """
        super().save_model(request, obj, form, change)

        if "pages" not in form.cleaned_data:
            return

        chosen = set(form.cleaned_data["pages"])
        current = set(obj.page_access.values_list("page_key", flat=True))

        obj.page_access.filter(page_key__in=current - chosen).delete()
        UserPageAccess.objects.bulk_create(
            [
                UserPageAccess(user=obj, page_key=key, granted_by=request.user)
                for key in sorted(chosen - current)
            ]
        )

    @admin.action(description="Выдать все разделы")
    def grant_all_pages(self, request, queryset):
        """Для нескольких людей сразу — форма правит одного."""
        created = 0
        for user in queryset:
            existing = set(user.page_access.values_list("page_key", flat=True))
            missing = [page.key for page in PAGES if page.key not in existing]
            UserPageAccess.objects.bulk_create(
                [
                    UserPageAccess(user=user, page_key=key, granted_by=request.user)
                    for key in missing
                ]
            )
            created += len(missing)
        self.message_user(request, f"Выдано разделов: {created}", messages.SUCCESS)

    @admin.action(description="Забрать все разделы")
    def revoke_all_pages(self, request, queryset):
        removed, _ = UserPageAccess.objects.filter(user__in=queryset).delete()
        self.message_user(
            request,
            f"Снято разделов: {removed}. Эти люди войдут и не увидят ничего.",
            messages.WARNING,
        )


@admin.register(WritebackSwitch)
class WritebackSwitchAdmin(admin.ModelAdmin):
    """Единственное место, где автоматическую запись в учёт выключают.

    Правится в админке, а не в настройках, намеренно: выключать приходится
    тогда, когда запись уже портит учёт, и ждать деплоя в этот момент нельзя.

    Строка на каждый вид записи. Сейчас вид один — себестоимость едет
    в тип цены карточки товара четыре раза в сутки.
    """

    list_display = ("kind", "enabled", "updated_at", "note")
    list_filter = ("enabled",)
    list_editable = ("enabled",)
    list_display_links = ("kind",)
    readonly_fields = ("updated_at",)


class WritebackChangeInline(admin.TabularInline):
    model = WritebackChange
    extra = 0
    can_delete = False
    fields = ("target_name", "field", "old_value", "new_value", "error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(WritebackRun)
class WritebackRunAdmin(admin.ModelAdmin):
    """Журнал: что система записала в МойСклад и чем это кончилось.

    Только чтение: правленная запись о записи в учёт бесполезна.

    «Рассмотрено» — сколько позиций проверили, «изменено» — сколько
    записали. Пропуск разбит на два: «значение неизвестно» (себестоимости
    нет) и «уже совпадает» (менять нечего). Их сумма равна общему пропуску.
    """

    list_display = (
        "started_at", "kind", "status", "dry_run",
        "considered", "changed",
        # Разбивка пропуска, а не одно число: «изменено 0, пропущено 315»
        # не отличало «всё уже сходится» от «запись не работает».
        "skipped_unknown", "skipped_equal",
        "failed", "request_count",
    )
    list_filter = ("kind", "status", "dry_run")
    date_hierarchy = "started_at"
    inlines = [WritebackChangeInline]
    readonly_fields = tuple(
        field.name for field in WritebackRun._meta.fields
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False



class SyncEntityInline(admin.TabularInline):
    """Итог по каждой сущности внутри прогона.

    Без него «синхронизация прошла» — слишком грубая правда: прогон,
    где отгрузки не доехали, выглядит так же, как удавшийся.
    """

    model = SyncEntityResult
    extra = 0
    can_delete = False
    fields = ("entity", "status", "fetched", "created", "updated", "marked_deleted", "error")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SyncRun)
class SyncRunAdmin(admin.ModelAdmin):
    """Журнал чтения из МойСклада. Только чтение — это запись о событии.

    Полезен ровно в тот день, когда синхронизация молча перестанет ходить:
    на экране страниц видна только отметка «данные на 12:23», и по ней
    не отличить «сегодня нечего было забирать» от «третий день не запускалось».
    """

    list_display = (
        "started_at", "kind", "status", "triggered_manually", "request_count", "error",
    )
    list_filter = ("kind", "status", "triggered_manually")
    date_hierarchy = "started_at"
    inlines = [SyncEntityInline]
    readonly_fields = tuple(field.name for field in SyncRun._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    """Журнал резервных копий.

    **«Проверен восстановлением» — единственная графа, которая что-то значит.**
    Пустой или обрезанный архив создаётся так же успешно, как настоящий,
    и отличить их по наличию файла нельзя.
    """

    list_display = (
        "started_at", "name", "status", "verified", "size_mb", "kept", "dry_run",
    )
    list_filter = ("status", "verified", "dry_run")
    date_hierarchy = "started_at"
    readonly_fields = tuple(field.name for field in BackupRun._meta.fields)

    @admin.display(description="Размер", ordering="size_bytes")
    def size_mb(self, run: BackupRun) -> str:
        if not run.size_bytes:
            return "—"
        return f"{run.size_bytes / 1024 / 1024:.1f} МБ"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# Группы Django в этом проекте не решают ничего: доступ к разделам определяет
# реестр `PAGES`, а в саму админку пускают только суперпользователя. Пункт
# меню, который ничего не делает, — это приглашение выдать доступ не тем
# способом и потом искать, почему он не сработал.
admin.site.unregister(Group)
