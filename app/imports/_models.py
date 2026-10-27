"""Результат проверки файла, который ещё не применён к данным."""

from typing import ClassVar, Literal

from app.domain import InputError, Issue, PriceRow, RequestRow, Schema

ImportKind = Literal["price", "request"]


class ParsedUpload(Schema):
    """Содержимое одного полностью проверенного CSV."""

    kind: ImportKind
    filename: str
    sha256: str
    rows: tuple[PriceRow, ...] | tuple[RequestRow, ...]
    warnings: tuple[Issue, ...] = ()
    request_id: str | None = None


class ImportErrorInfo(InputError):
    """Список ошибок файла с адресом каждой ячейки."""

    code: ClassVar[str] = "INVALID_CSV"

    def __init__(self, message: str, issues: tuple[Issue, ...] = ()) -> None:
        """Сохранить безопасное описание и подробности для интерфейса.

        Args:
            message: Публичный текст.
            issues: Ошибки конкретных ячеек.
        """
        super().__init__(message, issues=issues)
