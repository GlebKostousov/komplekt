"""Проверка контейнера файла до разбора строк CSV."""

import unicodedata

from ._models import ImportErrorInfo

MAX_BYTES = 1_048_576
ALLOWED_TYPES = {
    "",
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}


def _check_name(filename: str) -> str:
    """Разрешить только простое имя CSV без пути и скрытых символов."""
    unsafe = any(
        ord(char) < 32 or unicodedata.category(char) in {"Cc", "Cf", "Cs"}
        for char in filename
    )
    if unsafe or "/" in filename or "\\" in filename or len(filename) > 150:
        raise ImportErrorInfo(
            "Переименуйте файл: короткое имя без пути и скрытых "
            "символов, например price.csv."
        )
    if not filename.lower().endswith(".csv") or filename.lower() == ".csv":
        raise ImportErrorInfo(
            "Выберите файл CSV. Файлы Excel, PDF, изображения и "
            "архивы здесь не поддерживаются. Сохраните таблицу как "
            "CSV UTF-8."
        )
    return filename


def _check_size(payload: bytes) -> None:
    """Ограничить размер файла и отдельно сообщить о пустом файле."""
    if not payload:
        raise ImportErrorInfo(
            "Файл пуст. Добавьте заголовки и хотя бы одну строку данных."
        )
    if len(payload) > MAX_BYTES:
        raise ImportErrorInfo(
            "Файл больше 1 МБ. Оставьте нужную заявку или "
            "сократите прайс и загрузите его снова."
        )


def _check_type(payload: bytes, content_type: str) -> None:
    """Не принимать изображение, архив или документ под видом CSV."""
    mime = content_type.split(";", 1)[0].strip().lower()
    binary = payload.startswith(
        (
            b"%PDF",
            b"PK\x03\x04",
            b"\x89PNG",
            b"\xff\xd8\xff",
            b"MZ",
            b"\xd0\xcf\x11\xe0",
        )
    )
    if mime not in ALLOWED_TYPES or binary or b"\x00" in payload:
        raise ImportErrorInfo(
            "Это не текстовый CSV-файл. Откройте исходную таблицу "
            "и сохраните её как CSV UTF-8; простое переименование "
            "расширения не поможет."
        )


def decode_file(payload: bytes, filename: str, content_type: str) -> str:
    """Проверить имя, размер, содержимое и прочитать UTF-8, включая BOM."""
    _check_name(filename)
    _check_size(payload)
    _check_type(payload, content_type)
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ImportErrorInfo(
            "Файл сохранён в другой кодировке. Откройте таблицу и "
            "выберите «CSV UTF-8». Затем загрузите её снова."
        ) from error
