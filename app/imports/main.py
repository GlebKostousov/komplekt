"""Проверить CSV целиком, не изменяя текущий прайс или заявки."""

import hashlib
from typing import Literal

from app.domain import Issue, PriceRow, RequestRow

from ._file import MAX_BYTES, decode_file
from ._models import ImportErrorInfo, ImportKind, ParsedUpload
from ._rows import PRICE_HEADERS, REQUEST_HEADERS, parse_rows

__all__ = ["ImportErrorInfo", "ImportKind", "MAX_BYTES", "ParsedUpload", "parse_upload"]


def _duplicates(
    values: tuple[tuple[int, str | int], ...], field: str, label: str
) -> None:
    """Не разрешать затереть один артикул или номер строки другим."""
    seen: dict[str | int, int] = {}
    issues: list[Issue] = []
    for row, value in values:
        if value in seen:
            issues.append(
                Issue(
                    row=row,
                    field=field,
                    value=str(value),
                    message=(
                        f"{label} {value} уже встречается в строке {seen[value]}. "
                        "Исправьте значение или оставьте одну строку."
                    ),
                )
            )
        seen[value] = row
    _raise_duplicates(issues)


def _raise_duplicates(issues: list[Issue]) -> None:
    """Отклонить файл целиком при повторяющихся ключах."""
    if issues:
        raise ImportErrorInfo(
            "В файле есть повторяющиеся записи. Данные пока не обновлены.",
            tuple(issues[:50]),
        )


def _parse_price(text: str, filename: str, digest: str) -> ParsedUpload:
    """Проверить прайс и отдельно отметить отсутствующие цены."""
    located = parse_rows(text, PRICE_HEADERS, PriceRow, 2000)
    _duplicates(tuple((number, row.sku) for number, row in located), "sku", "Артикул")
    warnings = tuple(
        Issue(
            row=number,
            field="price",
            value="",
            message=(
                f"{row.name} ({row.sku}): цена не указана. "
                "После загрузки её можно добавить или оставить пустой; "
                "ноль подставлен не будет."
            ),
        )
        for number, row in located
        if row.price is None
    )
    return ParsedUpload(
        kind="price",
        filename=filename,
        sha256=digest,
        rows=tuple(row for _, row in located),
        warnings=warnings,
    )


def _parse_request(text: str, filename: str, digest: str) -> ParsedUpload:
    """Проверить одну заявку, её номер и уникальные номера позиций."""
    located = parse_rows(text, REQUEST_HEADERS, RequestRow, 200)
    request_id = located[0][1].request_id
    mixed = tuple(
        Issue(
            row=number,
            field="request_id",
            value=row.request_id,
            message=(
                f"В файле уже есть заявка {request_id}. "
                "Для другой заявки подготовьте отдельный CSV."
            ),
        )
        for number, row in located
        if row.request_id != request_id
    )
    if mixed:
        raise ImportErrorInfo(
            "В одном файле должна быть одна заявка. Данные пока не обновлены.",
            mixed[:50],
        )
    _duplicates(
        tuple((number, row.line) for number, row in located), "line", "Номер позиции"
    )
    return ParsedUpload(
        kind="request",
        filename=filename,
        sha256=digest,
        rows=tuple(row for _, row in located),
        request_id=request_id,
    )


def parse_upload(
    kind: Literal["price", "request"], payload: bytes, filename: str, content_type: str
) -> ParsedUpload:
    """Принять настоящий CSV, проверить все строки и вернуть готовое превью."""
    text = decode_file(payload, filename, content_type)
    digest = hashlib.sha256(payload).hexdigest()
    if kind == "price":
        return _parse_price(text, filename, digest)
    return _parse_request(text, filename, digest)
