"""Ожидаемые ошибки сохранения и поиска данных."""

from typing import ClassVar

from fastapi import status

from app.domain import QuoteError


class ConflictError(QuoteError):
    """Предупредить, что пользователь работает с устаревшими данными."""

    code: ClassVar[str] = "CONFLICT"
    http_status: ClassVar[int] = status.HTTP_409_CONFLICT


class NotFoundError(QuoteError):
    """Объяснить, что нужной записи больше нет."""

    code: ClassVar[str] = "NOT_FOUND"
    http_status: ClassVar[int] = status.HTTP_404_NOT_FOUND


class StorageError(QuoteError):
    """Не раскрывать пути и SQL при недоступности локальной базы."""

    code: ClassVar[str] = "STORAGE_ERROR"
    http_status: ClassVar[int] = status.HTTP_503_SERVICE_UNAVAILABLE
    public_message = (
        "Не удалось сохранить или прочитать данные. "
        "Проверьте свободное место и перезапустите приложение."
    )
