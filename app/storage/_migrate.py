"""Перенос локальной базы со старых JSON-таблиц на схему версии 1."""

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain import (
    BuyerDraft,
    Catalog,
    Product,
    QuoteSummary,
    RequestRecord,
    SavedQuote,
)

from ._ddl import SCHEMA
from ._quotes import save_quote
from ._records import replace_catalog, save_request

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_OLD_TABLES = (
    "quote_candidates",
    "quote_missing_fields",
    "quote_lines",
    "quotes",
    "request_choices",
    "request_selected",
    "request_lines",
    "requests",
    "products",
    "catalog",
)


@dataclass(frozen=True)
class _LegacyQuote:
    """Один документ из старой базы вместе с прежним номером."""

    sequence: int
    document: SavedQuote
    summary: QuoteSummary
    pdf: bytes


@dataclass(frozen=True)
class _Legacy:
    """Снимок старой базы до удаления JSON-таблиц."""

    catalog: Catalog | None
    requests: tuple[RequestRecord, ...]
    quotes: tuple[_LegacyQuote, ...]


def migrate(connection: sqlite3.Connection) -> None:
    """Привести базу к схеме версии 1.

    Args:
        connection: Соединение без внешней транзакции.
    """
    _ensure_migrations(connection)
    if _version(connection) >= 1:
        return
    connection.execute("BEGIN IMMEDIATE")
    _upgrade(connection)
    connection.commit()


def _ensure_migrations(connection: sqlite3.Connection) -> None:
    """Создать журнал версий, если его ещё нет.

    Args:
        connection: Открытое соединение.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def _version(connection: sqlite3.Connection) -> int:
    """Прочитать последнюю применённую версию.

    Args:
        connection: Открытое соединение.

    Returns:
        Номер версии или ноль, если переносов ещё не было.
    """
    row = connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _upgrade(connection: sqlite3.Connection) -> None:
    """Перенести данные внутри уже открытой транзакции.

    Args:
        connection: Транзакция ``BEGIN IMMEDIATE``.
    """
    if _version(connection) >= 1:
        return
    _rewrite(connection, _capture(connection))


def _rewrite(connection: sqlite3.Connection, legacy: _Legacy | None) -> None:
    """Заменить таблицы и записать прочитанный снимок.

    Args:
        connection: Открытая транзакция.
        legacy: Снимок старой базы или ``None``.
    """
    if legacy is not None:
        _drop_legacy(connection)
    _apply_schema(connection)
    _restore_if_needed(connection, legacy)
    _stamp(connection)


def _restore_if_needed(connection: sqlite3.Connection, legacy: _Legacy | None) -> None:
    """Записать старые данные, если они были прочитаны.

    Args:
        connection: Открытая транзакция.
        legacy: Снимок старой базы или ``None``.
    """
    if legacy is not None:
        _restore(connection, legacy)


def _capture(connection: sqlite3.Connection) -> _Legacy | None:
    """Прочитать старую базу, если товары ещё лежат в столбце ``data``.

    Args:
        connection: Открытая транзакция.

    Returns:
        Снимок или ``None`` для новой базы.
    """
    if not _has_data_column(connection):
        return None
    return _Legacy(
        _read_catalog(connection),
        _read_requests(connection),
        _read_quotes(connection),
    )


def _has_data_column(connection: sqlite3.Connection) -> bool:
    """Понять, что таблица товаров ещё старая.

    Args:
        connection: Открытая транзакция.

    Returns:
        ``True``, если есть столбец ``data``.
    """
    if not _table_exists(connection, "products"):
        return False
    return _column_exists(connection, "products", "data")


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    """Проверить, что таблица уже создана.

    Args:
        connection: Открытое соединение.
        name: Имя таблицы.

    Returns:
        ``True``, если таблица есть.
    """
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    """Проверить столбец по описанию таблицы.

    Args:
        connection: Открытое соединение.
        table: Имя таблицы из кода миграции.
        column: Имя столбца.

    Returns:
        ``True``, если столбец есть.
    """
    _identifier(table)
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
    return any(str(row[1]) == column for row in rows)


def _read_catalog(connection: sqlite3.Connection) -> Catalog | None:
    """Собрать прайс из старых метаданных и JSON товаров.

    Args:
        connection: Открытая транзакция.

    Returns:
        Прайс или ``None``.
    """
    row = connection.execute(
        "SELECT value FROM metadata WHERE key = 'catalog'"
    ).fetchone()
    if row is None:
        return None
    products = tuple(
        Product.model_validate_json(item[0])
        for item in connection.execute("SELECT data FROM products ORDER BY sku")
    )
    return Catalog.model_validate_json(row[0]).model_copy(update={"products": products})


def _read_requests(connection: sqlite3.Connection) -> tuple[RequestRecord, ...]:
    """Прочитать заявки в порядке сохранения.

    Args:
        connection: Открытая транзакция.

    Returns:
        Заявки от старых к новым.
    """
    rows = connection.execute("SELECT data FROM requests ORDER BY rowid ASC")
    loaded = (RequestRecord.model_validate_json(row[0]) for row in rows)
    return tuple(_with_drafts(record) for record in loaded)


def _with_drafts(record: RequestRecord) -> RequestRecord:
    """Скопировать сохранённые реквизиты и скидку в черновик формы.

    Args:
        record: Заявка из старой базы.

    Returns:
        Заявка с заполненным черновиком.
    """
    return record.model_copy(
        update={
            "buyer_draft": BuyerDraft.model_validate(record.buyer.model_dump()),
            "discount_draft": format(record.discount_percent, "f"),
        }
    )


def _read_quotes(connection: sqlite3.Connection) -> tuple[_LegacyQuote, ...]:
    """Прочитать документы, сохранив прежние номера.

    Args:
        connection: Открытая транзакция.

    Returns:
        Документы от старых к новым.
    """
    rows = connection.execute(
        "SELECT sequence, data, summary, pdf FROM quotes ORDER BY sequence"
    )
    return tuple(_legacy_quote(row) for row in rows)


def _legacy_quote(row: sqlite3.Row) -> _LegacyQuote:
    """Разобрать одну старую строку документа.

    Args:
        row: Строка таблицы ``quotes``.

    Returns:
        Документ с прежним номером.
    """
    return _LegacyQuote(
        sequence=int(row[0]),
        document=SavedQuote.model_validate_json(row[1]),
        summary=QuoteSummary.model_validate_json(row[2]),
        pdf=bytes(row[3]),
    )


def _drop_legacy(connection: sqlite3.Connection) -> None:
    """Удалить старые таблицы после чтения.

    Args:
        connection: Открытая транзакция.
    """
    for name in _OLD_TABLES:
        _drop_table(connection, name)


def _drop_table(connection: sqlite3.Connection, name: str) -> None:
    """Удалить одну таблицу из заранее известного списка.

    Args:
        connection: Открытая транзакция.
        name: Имя таблицы.
    """
    if name not in _OLD_TABLES:
        message = "Неизвестная таблица."
        raise RuntimeError(message)
    connection.execute(f"DROP TABLE IF EXISTS {name}")  # noqa: S608 — имя из списка


def _apply_schema(connection: sqlite3.Connection) -> None:
    """Создать таблицы версии 1 без отдельного коммита.

    Args:
        connection: Открытая транзакция.
    """
    for statement in _statements():
        connection.execute(statement)


def _statements() -> tuple[str, ...]:
    """Разбить текст схемы на отдельные операторы.

    Returns:
        Операторы без пустых хвостов.
    """
    return tuple(part.strip() for part in SCHEMA.split(";") if part.strip())


def _restore(connection: sqlite3.Connection, legacy: _Legacy) -> None:
    """Записать прочитанные данные в новые столбцы.

    Args:
        connection: Открытая транзакция.
        legacy: Снимок старой базы.
    """
    if legacy.catalog is not None:
        replace_catalog(connection, legacy.catalog)
    _restore_requests(connection, legacy.requests)
    _restore_quotes(connection, legacy.quotes)
    connection.execute("DELETE FROM metadata WHERE key = 'catalog'")


def _restore_requests(
    connection: sqlite3.Connection, requests: tuple[RequestRecord, ...]
) -> None:
    """Записать заявки в порядке их прежнего сохранения.

    Args:
        connection: Открытая транзакция.
        requests: Заявки от старых к новым.
    """
    for request in requests:
        save_request(connection, request)


def _restore_quotes(
    connection: sqlite3.Connection, quotes: tuple[_LegacyQuote, ...]
) -> None:
    """Записать документы с прежними номерами.

    Args:
        connection: Открытая транзакция.
        quotes: Документы от старых к новым.
    """
    for quote in quotes:
        save_quote(
            connection,
            quote.document,
            quote.summary,
            quote.pdf,
            None,
            quote.sequence,
        )


def _stamp(connection: sqlite3.Connection) -> None:
    """Отметить, что схема версии 1 применена.

    Args:
        connection: Открытая транзакция.
    """
    connection.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (1, ?)",
        (datetime.now(UTC).isoformat(timespec="seconds"),),
    )


def _identifier(name: str) -> None:
    """Отклонить имя, которое нельзя подставить в PRAGMA.

    Args:
        name: Имя таблицы.
    """
    if _NAME.fullmatch(name) is None:
        message = "Некорректное имя таблицы."
        raise RuntimeError(message)
