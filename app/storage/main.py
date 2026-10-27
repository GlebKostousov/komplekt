"""Предоставить локальные транзакции с проверкой версии данных."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.logging import get_logger

from ._errors import ConflictError, NotFoundError, StorageError
from ._migrate import migrate
from ._schema import PendingImport
from ._transaction import Transaction

__all__ = [
    "ConflictError",
    "NotFoundError",
    "PendingImport",
    "Repository",
    "StorageError",
    "Transaction",
]


class Repository:
    """Открывать отдельное соединение SQLite для каждой операции."""

    def __init__(self, path: Path) -> None:
        """Сохранить путь к базе.

        Args:
            path: Файл SQLite.
        """
        self.path = path

    def initialize(self) -> None:
        """Создать локальную базу и применить версию схемы."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL").fetchone()
            migrate(connection)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Закрывать соединение и не раскрывать SQL в тексте ошибки.

        Yields:
            Соединение с включёнными внешними ключами.

        Raises:
            StorageError: База недоступна.
        """
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        except sqlite3.Error as error:
            get_logger(__name__).error(
                "storage.failed", error_type=type(error).__name__
            )
            raise StorageError(internal_message=type(error).__name__) from error
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[Transaction]:
        """Прочитать согласованный снимок без изменения базы.

        Yields:
            Транзакция чтения.
        """
        with self._connection() as connection:
            connection.execute("BEGIN")
            try:
                yield Transaction(connection)
            finally:
                connection.rollback()

    @contextmanager
    def write(
        self,
        revision: int,
        *,
        advance: bool = True,
        idempotency_key: str | None = None,
    ) -> Iterator[Transaction]:
        """Сохранить изменения целиком либо оставить прежние данные.

        Args:
            revision: Номер данных, которые видел пользователь.
            advance: Нужно ли увеличить номер после изменения рабочих данных.
            idempotency_key: Ключ повтора выпуска КП. Если документ уже есть,
                проверка версии пропускается и номер не растёт.

        Yields:
            Транзакция записи.

        Raises:
            ConflictError: Другой запрос уже изменил рабочие данные.
        """
        with self._connection() as connection:
            with self._locked(
                connection, revision, advance, idempotency_key
            ) as transaction:
                yield transaction

    @contextmanager
    def _locked(
        self,
        connection: sqlite3.Connection,
        revision: int,
        advance: bool,
        idempotency_key: str | None,
    ) -> Iterator[Transaction]:
        """Держать запись до коммита или отката.

        Args:
            connection: Соединение.
            revision: Номер данных пользователя.
            advance: Увеличивать ли номер.
            idempotency_key: Ключ повтора.

        Yields:
            Транзакция.
        """
        connection.execute("BEGIN IMMEDIATE")
        transaction = Transaction(connection)
        try:
            replay = self._prepare(transaction, revision, idempotency_key)
            yield transaction
            if not replay:
                self._finish(transaction, advance)
            connection.commit()
        finally:
            connection.rollback()

    @staticmethod
    def _prepare(
        transaction: Transaction, revision: int, idempotency_key: str | None
    ) -> bool:
        """Пропустить проверку версии, если этот выпуск уже сохранён.

        Args:
            transaction: Открытая транзакция.
            revision: Номер данных пользователя.
            idempotency_key: Ключ повтора.

        Returns:
            ``True``, если документ с этим ключом уже есть.
        """
        if _remember_replay(transaction, idempotency_key):
            return True
        Repository._check_revision(transaction, revision)
        return False

    @staticmethod
    def _check_revision(transaction: Transaction, revision: int) -> None:
        """Отвергнуть изменение устаревшего состояния.

        Args:
            transaction: Открытая транзакция.
            revision: Номер данных пользователя.

        Raises:
            ConflictError: Номер уже другой.
        """
        if transaction.revision() != revision:
            raise ConflictError(
                "Данные уже изменились в другой вкладке. "
                "Обновите страницу, проверьте новые значения и повторите действие."
            )

    @staticmethod
    def _finish(transaction: Transaction, advance: bool) -> None:
        """Обновить номер только для изменений рабочих данных.

        Args:
            transaction: Открытая транзакция.
            advance: Увеличивать ли номер.
        """
        if advance:
            transaction.advance()


def _remember_replay(transaction: Transaction, idempotency_key: str | None) -> bool:
    """Запомнить уже выпущенный документ с тем же ключом.

    Args:
        transaction: Открытая транзакция.
        idempotency_key: Ключ повтора.

    Returns:
        ``True``, если документ найден.
    """
    if idempotency_key is None:
        return False
    found = transaction.quote_id_for_key(idempotency_key)
    transaction.replay_id = found
    return found is not None
