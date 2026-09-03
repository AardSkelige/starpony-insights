from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import (
    User,
    UserPageAccess,
    WritebackChange,
    WritebackRun,
    WritebackSwitch,
)


class UserPageAccessInline(admin.TabularInline):
    model = UserPageAccess
    fk_name = "user"
    extra = 0
    fields = ("page_key", "granted_at", "granted_by")
    readonly_fields = ("granted_at",)


@admin.register(User)
class UserAdminWithAccess(UserAdmin):
    inlines = [UserPageAccessInline]


@admin.register(WritebackSwitch)
class WritebackSwitchAdmin(admin.ModelAdmin):
    """Единственное место, где обратную запись выключают.

    Правится в админке, а не в настройках, намеренно: выключать приходится
    тогда, когда запись уже портит учёт, и ждать деплоя в этот момент нельзя.
    """

    list_display = ("kind", "enabled", "updated_at", "note")
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
    """Журнал. Только чтение: правленная запись о записи в учёт бесполезна."""

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
