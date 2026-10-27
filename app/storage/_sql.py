"""Параметризованная запись строк в заранее известные таблицы."""

import re
import sqlite3
from collections.abc import Mapping

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_TABLES = frozenset(
    {
        "catalog",
        "products",
        "quote_candidates",
        "quote_lines",
        "quote_missing_fields",
        "quotes",
        "request_choices",
        "request_lines",
        "request_selected",
        "requests",
    }
)


def insert(
    connection: sqlite3.Connection, table: str, row: Mapping[str, object]
) -> None:
    """Вставить одну строку. Имена таблицы и столбцов не приходят от пользователя.

    Args:
        connection: Открытая транзакция.
        table: Имя таблицы из белого списка.
        row: Значения по именам столбцов.
    """
    connection.execute(_statement("INSERT INTO", table, row), row)


def upsert(
    connection: sqlite3.Connection,
    table: str,
    row: Mapping[str, object],
    key: str,
) -> None:
    """Вставить строку или заменить её столбцы при том же ключе.

    Args:
        connection: Открытая транзакция.
        table: Имя таблицы из белого списка.
        row: Значения по именам столбцов.
        key: Столбец конфликта.
    """
    _ident(key)
    names = _names(row)
    assignments = ", ".join(
        f"{name} = excluded.{name}" for name in names if name != key
    )
    statement = (
        f"{_statement('INSERT INTO', table, row)} "
        f"ON CONFLICT({key}) DO UPDATE SET {assignments}"
    )
    connection.execute(statement, row)


def _statement(prefix: str, table: str, row: Mapping[str, object]) -> str:
    """Собрать INSERT с именованными параметрами.

    Args:
        prefix: Начало оператора.
        table: Имя таблицы.
        row: Строка значений.

    Returns:
        Текст оператора.
    """
    if table not in _TABLES:
        message = "Неизвестная таблица записи."
        raise RuntimeError(message)
    names = _names(row)
    columns = ", ".join(names)
    holders = ", ".join(f":{name}" for name in names)
    return f"{prefix} {table} ({columns}) VALUES ({holders})"


def _names(row: Mapping[str, object]) -> tuple[str, ...]:
    """Проверить имена столбцов.

    Args:
        row: Строка значений.

    Returns:
        Имена в исходном порядке.
    """
    names = tuple(row)
    for name in names:
        _ident(name)
    return names


def _ident(name: str) -> None:
    """Отклонить имя, которое не является простым идентификатором SQL.

    Args:
        name: Имя таблицы или столбца.
    """
    if _NAME.fullmatch(name) is None:
        message = "Некорректное имя столбца."
        raise RuntimeError(message)
