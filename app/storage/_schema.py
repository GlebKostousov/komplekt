"""Служебная запись проверенного файла до подтверждения загрузки."""

from typing import Literal

from app.domain import Schema


class PendingImport(Schema):
    """Хранить проверенный файл до подтверждения пользователя."""

    token: str
    kind: Literal["price", "request"]
    filename: str
    content_type: str
    payload: bytes
    revision: int
    expires_at: str
