"""Читать и менять записи внутри одной транзакции."""

import sqlite3

from app.domain import Catalog, Product, QuoteSummary, RequestRecord, SavedQuote

from ._errors import NotFoundError
from ._quotes import (
    load_pdf,
    load_quote,
    load_summaries,
    quote_id_for_key,
    save_quote,
)
from ._records import (
    find_request,
    load_catalog,
    load_product,
    load_requests,
    replace_catalog,
    save_product,
    save_request,
)
from ._schema import PendingImport


class Transaction:
    """Объединить изменения, которые должны сохраниться вместе."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        """Получить соединение, сроком жизни которого управляет Repository.

        Args:
            connection: Открытая транзакция.
        """
        self.connection = connection
        self.replay_id: str | None = None

    def revision(self) -> int:
        """Прочитать номер последнего изменения рабочей области.

        Returns:
            Номер версии данных.
        """
        row = self.connection.execute(
            "SELECT value FROM metadata WHERE key = 'revision'"
        ).fetchone()
        return int(row[0])

    def advance(self) -> None:
        """Увеличить номер изменения в той же транзакции."""
        self.connection.execute(
            "UPDATE metadata SET value = CAST(value AS INTEGER) + 1 "
            "WHERE key = 'revision'"
        )

    def quote_id_for_key(self, key: str) -> str | None:
        """Найти документ, уже выпущенный с этим ключом повтора.

        Args:
            key: Ключ идемпотентности.

        Returns:
            Идентификатор документа или ``None``.
        """
        return quote_id_for_key(self.connection, key)

    def catalog(self) -> Catalog | None:
        """Прочитать текущий прайс.

        Returns:
            Прайс или ``None``.
        """
        return load_catalog(self.connection)

    def replace_catalog(self, catalog: Catalog) -> None:
        """Полностью заменить товары и сбросить прежние ручные соответствия.

        Args:
            catalog: Новый прайс.
        """
        replace_catalog(self.connection, catalog)

    def product(self, product_id: str) -> Product:
        """Найти товар только в текущем прайсе.

        Args:
            product_id: Идентификатор сущности.

        Returns:
            Товар.
        """
        return load_product(self.connection, product_id)

    def save_product(self, product: Product) -> None:
        """Сохранить цену текущего товара.

        Args:
            product: Товар с новой ценой.
        """
        save_product(self.connection, product)

    def requests(self) -> tuple[RequestRecord, ...]:
        """Прочитать заявки, начиная с последней сохранённой.

        Returns:
            Заявки.
        """
        return load_requests(self.connection)

    def find_request(self, request_id: str) -> RequestRecord | None:
        """Найти ранее загруженную заявку.

        Args:
            request_id: Номер заявки.

        Returns:
            Заявка или ``None``.
        """
        return find_request(self.connection, request_id)

    def request(self, request_id: str) -> RequestRecord:
        """Вернуть заявку или понятную ошибку отсутствия.

        Args:
            request_id: Номер заявки.

        Returns:
            Заявка.

        Raises:
            NotFoundError: Заявки нет.
        """
        result = self.find_request(request_id)
        if result is None:
            raise NotFoundError("Заявка не найдена. Сначала загрузите её CSV-файл.")
        return result

    def save_request(self, request: RequestRecord) -> None:
        """Обновить заявку по её номеру или добавить новую.

        Args:
            request: Заявка целиком.
        """
        save_request(self.connection, request)

    def summaries(self) -> tuple[QuoteSummary, ...]:
        """Прочитать историю выпущенных документов, начиная с новых.

        Returns:
            Строки истории.
        """
        return load_summaries(self.connection)

    def next_number(self) -> int:
        """Получить следующий номер под блокировкой транзакции.

        Returns:
            Следующий порядковый номер.
        """
        row = self.connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM quotes"
        ).fetchone()
        return int(row[0])

    def save_quote(
        self,
        document: SavedQuote,
        summary: QuoteSummary,
        pdf: bytes,
        idempotency_key: str | None = None,
    ) -> None:
        """Сохранить снимок и точные байты PDF вместе.

        Args:
            document: Полный снимок.
            summary: Строка истории.
            pdf: Байты файла.
            idempotency_key: Ключ повтора. Пусто только при переносе старой базы.
        """
        save_quote(self.connection, document, summary, pdf, idempotency_key)

    def quote(self, quote_id: str) -> SavedQuote:
        """Прочитать неизменяемый снимок документа.

        Args:
            quote_id: Идентификатор документа.

        Returns:
            Снимок.
        """
        return load_quote(self.connection, quote_id)

    def pdf(self, quote_id: str) -> tuple[str, bytes]:
        """Получить ранее сохранённый PDF без нового расчёта.

        Args:
            quote_id: Идентификатор документа.

        Returns:
            Имя файла и содержимое.
        """
        return load_pdf(self.connection, quote_id)

    def remember_import(self, pending: PendingImport, now: str) -> None:
        """Сохранить файл до подтверждения и убрать истёкшие загрузки.

        Args:
            pending: Проверенный файл.
            now: Текущее время в UTC.
        """
        self.connection.execute(
            "DELETE FROM pending_imports WHERE expires_at < ?", (now,)
        )
        self.connection.execute(
            "DELETE FROM pending_imports WHERE token IN "
            "(SELECT token FROM pending_imports ORDER BY rowid DESC LIMIT -1 OFFSET 19)"
        )
        self.connection.execute(
            "INSERT INTO pending_imports VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                pending.token,
                pending.kind,
                pending.filename,
                pending.content_type,
                pending.payload,
                pending.revision,
                pending.expires_at,
            ),
        )

    def pending_import(self, token: str) -> PendingImport:
        """Прочитать только ранее проверенную загрузку.

        Args:
            token: Ключ проверки.

        Returns:
            Загрузка.

        Raises:
            NotFoundError: Проверка устарела или уже применена.
        """
        row = self.connection.execute(
            "SELECT * FROM pending_imports WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            raise NotFoundError(
                "Проверка файла устарела или уже применена. Загрузите файл ещё раз."
            )
        return PendingImport.model_validate(dict(row))

    def forget_import(self, token: str) -> None:
        """Убрать применённый файл, чтобы его нельзя было применить дважды.

        Args:
            token: Ключ проверки.
        """
        self.connection.execute("DELETE FROM pending_imports WHERE token = ?", (token,))
