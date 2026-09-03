"""Подмена главной страницы админки.

Отдельным модулем, а не в `core/apps.py`: два `AppConfig` в одном модуле
Django принимает за две попытки объявить умолчание приложения и отказывается
запускаться вовсе.
"""

from django.contrib.admin.apps import AdminConfig


class InsightsAdminConfig(AdminConfig):
    """Своя главная админки — с разделами по смыслу.

    Подменяется через `INSTALLED_APPS`, штатным способом Django:
    `admin.site` становится нашим сайтом, и `@admin.register`
    продолжает работать без единой правки.
    """

    default_site = "core.admin_site.InsightsAdminSite"
