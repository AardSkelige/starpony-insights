"""Настройки StarPony Insights.

Всё, что различается между машинами, приходит из окружения. Ни одного адреса,
протокола или пароля в коде: захардкоженный `http://` в списке доверенных
источников — классическая мина, взрывающаяся при переходе на HTTPS.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --- Основное ---------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY обязателен: задайте его в окружении или backend/.env")

DEBUG = env_bool("DEBUG", False)

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

# Проверка здоровья контейнера обращается к приложению изнутри, по 127.0.0.1,
# и без этого адреса Django отвечает ей 400 — контейнер считается больным,
# хотя работает. Снаружи адрес недостижим: наружу смотрит только прокси,
# и он передаёт настоящее имя домена.
for _internal in ("127.0.0.1", "localhost"):
    if _internal not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_internal)

# Домены со схемой: "https://insight.star-pony.ru". Схема приходит из окружения
# целиком, чтобы переход на HTTPS не требовал правки кода.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    # Статика Swagger UI. Стоит выше staticfiles: приложение отдаёт свои файлы,
    # и порядок здесь определяет, чьи найдутся первыми.
    "drf_spectacular_sidecar",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "core",
    "api",
    # Своих моделей нет — зеркало живёт в core.models. Приложение нужно, чтобы
    # Django нашёл management-команды синхронизации.
    "moysklad",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "api.middleware.PageAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- База данных ------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "starpony"),
        "USER": os.getenv("POSTGRES_USER", "starpony"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        # Соединение переживает запрос: gunicorn держит воркеры долго, а
        # переподключение к Postgres на каждый запрос — заметная доля времени
        # ответа на списочных страницах.
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Пользователи -----------------------------------------------------------

# Своя модель с первой миграции: подменить AUTH_USER_MODEL позже — это ручная
# пересборка внешних ключей на боевой базе.
AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- Локаль -----------------------------------------------------------------

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# --- Статика ----------------------------------------------------------------

# Не "static/": по этому пути фронтенд и админка Django столкнулись бы на одном
# домене, и прокси пришлось бы разбирать, чей файл запрашивают. Своя приставка
# снимает вопрос целиком — за ней стоит только админка.
STATIC_URL = "django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Безопасность -----------------------------------------------------------

# За прокси Django не видит, что снаружи был HTTPS, и считает соединение
# небезопасным: тогда Secure-куки не ставятся, а redirect зацикливается.
if env_bool("BEHIND_TLS_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_HTTPONLY = True

# HSTS выдаётся браузеру на указанный срок и до его конца не отзывается. Поэтому
# срок задаётся окружением и по умолчанию равен нулю: включать осознанно, сначала
# на минуты, потом на год. Preload не включаем никогда — из него выходят месяцами.
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# --- API --------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Закрыто по умолчанию: эндпоинт, забывший объявить права, оказывается
    # недоступным, а не открытым всем.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "StarPony Insights API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Файлы страницы берутся из установленного пакета, а не с cdn.jsdelivr.net.
    # На CDN стоял тег @latest: версия сменилась бы сама, и страница сломалась
    # бы без единой правки с нашей стороны.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
}

# --- Логи -------------------------------------------------------------------

# В stdout: в контейнере логи забирает Docker, файлы на диске ему не нужны.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
