"""Выгрузка: тип XLSX и имя файла. Общее для всех разделов."""

from datetime import date

from django.utils import timezone

# Тип задаётся явно: FileResponse угадывает его по имени файла, а поток
# в памяти имени не имеет — и книга уезжает как application/octet-stream,
# который Excel открывать отказывается.
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def export_name(title: str, date_from: date | None, date_to: date | None) -> str:
    """Имя файла говорит, что внутри и когда снято.

    Одной даты выгрузки мало: две выборки за разные периоды, скачанные
    в один день, получили бы одинаковое имя. Поэтому в имени — период данных,
    а дата выгрузки идёт следом.
    """
    if date_from and date_to:
        period = f"{date_from:%d.%m.%Y}—{date_to:%d.%m.%Y}"
    elif date_from:
        period = f"с {date_from:%d.%m.%Y}"
    elif date_to:
        period = f"по {date_to:%d.%m.%Y}"
    else:
        period = "весь период"

    return f"{title}, {period} (выгружено {timezone.localdate():%d.%m.%Y}).xlsx"
