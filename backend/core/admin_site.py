"""Главная админки: разделы по смыслу, а не по приложениям Django.

Django группирует модели по приложению, и всё наше оказывалось одной кучей
«StarPony Insights»: пользователи вперемешку с выключателями записи в учёт.
Человек заходит сюда с одним из двух вопросов — «кому что открыть» или
«что там наши скрипты», — и раздел обязан отвечать на них, а не называть
внутреннее устройство.

Разделы объявлены здесь списком, а не выводятся из моделей: порядок
и названия — решение о том, как читается эта страница, и выводить его
не из чего.
"""

from django.contrib import admin

# Слаг, название, модели в порядке показа. Модель, не названная здесь,
# остаётся в разделе своего приложения: забывчивость не должна прятать
# страницу из админки.
#
# **Слаг латиницей и обязателен.** Django подставляет `app_label` в `id`
# и `aria-describedby` разметки: русское название с пробелами даёт
# `id="Люди и доступы-user"`, а `aria-describedby` разбирается по пробелам —
# и ссылки «Добавить»/«Изменить» начинают указывать на три несуществующих
# идентификатора. Заодно `class="app-Люди и доступы"` превращается в три
# класса вместо одного.
SECTIONS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("people", "Люди и доступы", ("core.User",)),
    # Что включено и настраивается. Выключателя у бэкапа здесь нет
    # намеренно: выключить бэкап тихо — ровно то, чего не должно быть
    # возможно одним щелчком.
    ("automation", "Автоматизация", ("core.WritebackSwitch",)),
    # Что происходило. Раздел говорит «журнал», строка — чего именно:
    # «Журнал: журнал синхронизации» никто не читает.
    (
        "journals",
        "Журналы",
        ("core.SyncRun", "core.WritebackRun", "core.BackupRun"),
    ),
)


class InsightsAdminSite(admin.AdminSite):
    site_header = "StarPony Insights"
    site_title = "StarPony Insights"
    index_title = "Управление"

    def get_app_list(self, request, app_label=None):
        """Разложить модели по разделам вместо приложений.

        При `app_label` — это страница одного приложения, а не главная;
        там перекладывать нечего, и поведение остаётся стандартным.
        """
        if app_label:
            return super().get_app_list(request, app_label)

        app_dict = self._build_app_dict(request)
        by_key = {
            f"{app['app_label']}.{model['object_name']}": model
            for app in app_dict.values()
            for model in app["models"]
        }

        result = []
        placed: set[str] = set()
        for slug, title, keys in SECTIONS:
            models = [by_key[key] for key in keys if key in by_key]
            if not models:
                continue
            placed.update(keys)
            result.append(
                {
                    "name": title,
                    "app_label": slug,
                    # Адрес первой модели раздела, а не пустая строка.
                    # Шаблон сравнивает `app.app_url in request.path`,
                    # и пустая строка входит в любой путь — все разделы
                    # разом подсвечивались как текущий, а заголовок был
                    # ссылкой в никуда. С настоящим адресом подсветка
                    # начинает означать то, что должна: «вы сейчас здесь».
                    "app_url": models[0].get("admin_url") or "",
                    "has_module_perms": True,
                    "models": models,
                }
            )

        # Всё, что не разложено: чужие приложения и наши модели, о которых
        # здесь забыли. Показать их обязательно — иначе модель исчезает
        # из админки молча, и заметить это можно только по её отсутствию.
        for app in sorted(app_dict.values(), key=lambda item: item["name"].lower()):
            rest = [
                model
                for model in app["models"]
                if f"{app['app_label']}.{model['object_name']}" not in placed
            ]
            if rest:
                result.append({**app, "models": rest})

        return result
