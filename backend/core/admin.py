from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import User, UserPageAccess


class UserPageAccessInline(admin.TabularInline):
    model = UserPageAccess
    fk_name = "user"
    extra = 0
    fields = ("page_key", "granted_at", "granted_by")
    readonly_fields = ("granted_at",)


@admin.register(User)
class UserAdminWithAccess(UserAdmin):
    inlines = [UserPageAccessInline]
