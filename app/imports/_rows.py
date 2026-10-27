"""Прочитать все строки и собрать ошибки до изменения данных."""

import csv
from collections import Counter
from collections.abc import Iterator
from io import StringIO
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.domain import Issue

from ._messages import issue_from_error
from ._models import ImportErrorInfo

REQUEST_HEADERS = ("request_id", "line", "sku", "name", "quantity", "unit")
PRICE_HEADERS = (
    "sku",
    "name",
    "unit",
    "pack_size",
    "price",
    "price_basis",
    "vat_rate",
    "source",
)
MAX_ISSUES = 50


class CsvReader(Protocol):
    """Минимальный контракт стандартного CSV-итератора."""

    line_num: int

    def __iter__(self) -> Iterator[list[str]]:
        """Вернуть строки CSV."""
        ...


def _header(values: list[str], expected: tuple[str, ...]) -> list[str]:
    """Проверить заголовки, допустив любой порядок колонок."""
    values = [value.strip() for value in values]
    repeated = [key for key, count in Counter(values).items() if count > 1]
    if repeated:
        raise ImportErrorInfo(
            f"Заголовки повторяются: {', '.join(repeated[:5])}. "
            "Оставьте каждый столбец один раз."
        )
    if set(values) != set(expected):
        raise ImportErrorInfo(
            "Первая строка должна содержать заголовки: "
            + ";".join(expected)
            + ". Разделяйте столбцы точкой с запятой (;). Скачать "
            "пример можно рядом с загрузкой."
        )
    return values


def _validate[T: BaseModel](
    values: list[str], header: list[str], model: type[T], row: int
) -> tuple[T | None, tuple[Issue, ...]]:
    """Проверить одну строку с физическим номером строки файла."""
    if len(values) != len(header):
        return None, (
            Issue(
                row=row,
                message=(
                    f"В строке {len(values)} ячеек, а нужно {len(header)}. "
                    "Проверьте точки с запятой; текст с точкой с запятой "
                    "заключите в двойные кавычки."
                ),
            ),
        )
    try:
        return model.model_validate(dict(zip(header, values, strict=True))), ()
    except ValidationError as error:
        return None, tuple(issue_from_error(item, row) for item in error.errors())


def _finish[T: BaseModel](
    rows: list[tuple[int, T]], issues: list[Issue]
) -> tuple[tuple[int, T], ...]:
    """Отклонить весь файл при ошибках; не возвращать частичный набор."""
    if issues:
        raise ImportErrorInfo(
            _issue_message(len(issues)),
            tuple(issues[:MAX_ISSUES]),
        )
    if not rows:
        raise ImportErrorInfo(
            "В файле есть заголовки, но нет товаров. Добавьте хотя "
            "бы одну строку данных."
        )
    return tuple(rows)


def _issue_message(count: int) -> str:
    """Объяснить следующий шаг без лишних предупреждений для короткого списка."""
    message = (
        "Данные пока не обновлены. Исправьте отмеченные ячейки "
        "и загрузите файл ещё раз."
    )
    if count > MAX_ISSUES:
        message += (
            " Показаны первые 50 замечаний; остальные появятся после исправления."
        )
    return message


def parse_rows[T: BaseModel](
    text: str, headers: tuple[str, ...], model: type[T], limit: int
) -> tuple[tuple[int, T], ...]:
    """Прочитать ограниченный CSV, сохранив физические номера строк."""
    reader = csv.reader(StringIO(text, newline=""), delimiter=";", strict=True)
    rows: list[tuple[int, T]] = []
    issues: list[Issue] = []
    try:
        header = _header(next(reader, []), headers)
        rows, issues = _read_values(reader, header, model, limit)
    except csv.Error as error:
        raise ImportErrorInfo(
            "Не удалось разобрать CSV. Проверьте двойные кавычки и "
            "разделители столбцов.",
            (
                Issue(
                    row=reader.line_num,
                    message="Проверьте кавычки в этой строке и в строках перед ней.",
                ),
            ),
        ) from error
    return _finish(rows, issues)


def _read_values[T: BaseModel](
    reader: CsvReader, header: list[str], model: type[T], limit: int
) -> tuple[list[tuple[int, T]], list[Issue]]:
    """Собрать строки, не прерываясь на первой неверной ячейке."""
    rows: list[tuple[int, T]] = []
    issues: list[Issue] = []
    for count, values in enumerate(filter(None, reader), 1):
        if count > limit:
            raise ImportErrorInfo(
                f"В этом файле больше {limit} строк данных. "
                "Сократите таблицу и загрузите её снова."
            )
        result, errors = _validate(values, header, model, reader.line_num)
        issues.extend(errors[: max(0, MAX_ISSUES + 1 - len(issues))])
        _append_valid(rows, result, reader.line_num)
    return rows, issues


def _append_valid[T: BaseModel](
    rows: list[tuple[int, T]], result: T | None, number: int
) -> None:
    """Сохранить строку только после успешной проверки схемы."""
    if result is not None:
        rows.append((number, result))
