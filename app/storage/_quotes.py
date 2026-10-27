"""Неизменяемый снимок КП по столбцам, без JSON-документа."""

import sqlite3

from app.domain import (
    Buyer,
    Draft,
    Product,
    QuoteLine,
    QuoteSummary,
    RequestRow,
    SavedQuote,
    Seller,
    SourceFile,
    Status,
)

from ._errors import NotFoundError
from ._money import (
    basis_points,
    from_basis_points,
    from_kopecks,
    kopecks,
    money_required,
)
from ._sql import insert

_BUYER = (
    "company_name",
    "inn",
    "kpp",
    "ogrn",
    "address",
    "contact_name",
    "email",
    "phone",
    "bank_name",
    "bik",
    "account",
    "correspondent_account",
)
_SELLER = (
    *_BUYER[:4],
    "address",
    "phone",
    "email",
    "website",
    "bank_name",
    "bik",
    "account",
    "correspondent_account",
    "manager",
    "manager_title",
)


def quote_id_for_key(connection: sqlite3.Connection, key: str) -> str | None:
    """Найти уже выпущенный документ с тем же ключом повтора.

    Args:
        connection: Открытая транзакция.
        key: Ключ идемпотентности.

    Returns:
        Идентификатор документа или ``None``.
    """
    row = connection.execute(
        "SELECT id FROM quotes WHERE idempotency_key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    return str(row["id"])


def load_summaries(connection: sqlite3.Connection) -> tuple[QuoteSummary, ...]:
    """Прочитать историю документов от новых к старым.

    Args:
        connection: Открытая транзакция.

    Returns:
        Краткие строки истории.
    """
    rows = connection.execute(
        "SELECT id, number, created_at, request_id, buyer_name, "
        "subtotal_kopecks, vat_kopecks, is_complete, selected_count, "
        "unresolved_count, filename FROM quotes ORDER BY sequence DESC"
    )
    return tuple(_summary(row) for row in rows)


def load_quote(connection: sqlite3.Connection, quote_id: str) -> SavedQuote:
    """Собрать сохранённый снимок.

    Args:
        connection: Открытая транзакция.
        quote_id: Идентификатор документа.

    Returns:
        Снимок, из которого был сделан PDF.

    Raises:
        NotFoundError: Документа нет.
    """
    header = connection.execute(
        "SELECT * FROM quotes WHERE id = ?", (quote_id,)
    ).fetchone()
    if header is None:
        raise NotFoundError("КП не найдено. Откройте раздел «История КП».")
    return _saved(connection, header)


def load_pdf(connection: sqlite3.Connection, quote_id: str) -> tuple[str, bytes]:
    """Вернуть имя и байты ранее сохранённого PDF.

    Args:
        connection: Открытая транзакция.
        quote_id: Идентификатор документа.

    Returns:
        Имя файла и содержимое.

    Raises:
        NotFoundError: Документа нет.
    """
    row = connection.execute(
        "SELECT filename, pdf FROM quotes WHERE id = ?", (quote_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("PDF не найден. Откройте раздел «История КП».")
    return str(row["filename"]), bytes(row["pdf"])


def save_quote(
    connection: sqlite3.Connection,
    document: SavedQuote,
    summary: QuoteSummary,
    pdf: bytes,
    idempotency_key: str | None,
    sequence: int | None = None,
) -> None:
    """Записать снимок, историю и байты PDF одной вставкой.

    Args:
        connection: Открытая транзакция.
        document: Полный снимок.
        summary: Строка истории.
        pdf: Байты файла.
        idempotency_key: Ключ повтора выпуска. Пусто у документов из старой базы.
        sequence: Номер для переноса старой базы. Пусто — следующий номер.
    """
    row = _quote_row(document, summary, pdf, idempotency_key)
    if sequence is not None:
        row["sequence"] = sequence
    insert(connection, "quotes", row)
    _insert_lines(connection, document)


def _saved(connection: sqlite3.Connection, header: sqlite3.Row) -> SavedQuote:
    """Собрать документ из заголовка и строк.

    Args:
        connection: Открытая транзакция.
        header: Строка таблицы документов.

    Returns:
        Снимок.
    """
    quote_id = str(header["id"])
    grouped = _candidates(connection, quote_id)
    lines = tuple(
        _line(row, tuple(grouped.get(int(row["position"]), ())))
        for row in connection.execute(
            "SELECT * FROM quote_lines WHERE quote_id = ? ORDER BY position",
            (quote_id,),
        )
    )
    missing = tuple(
        str(row["field"])
        for row in connection.execute(
            "SELECT field FROM quote_missing_fields WHERE quote_id = ? ORDER BY field",
            (quote_id,),
        )
    )
    return SavedQuote(
        id=quote_id,
        number=header["number"],
        created_at=header["created_at"],
        seller=_seller(header),
        quote=_draft(header, lines, missing),
    )


def _draft(
    header: sqlite3.Row, lines: tuple[QuoteLine, ...], missing: tuple[str, ...]
) -> Draft:
    """Собрать расчёт из столбцов заголовка.

    Args:
        header: Строка документа.
        lines: Строки расчёта.
        missing: Незаполненные поля покупателя.

    Returns:
        Расчёт на момент выпуска.
    """
    return Draft(
        request_id=header["request_id"],
        lines=lines,
        discount_percent=from_basis_points(int(header["discount_bp"])),
        vat_rate=from_basis_points(int(header["vat_bp"])),
        currency=header["currency"],
        confirmed_count=header["confirmed_count"],
        unresolved_count=header["unresolved_count"],
        is_complete=bool(header["is_complete"]),
        subtotal_with_vat=money_required(int(header["subtotal_kopecks"])),
        vat_amount=money_required(int(header["vat_kopecks"])),
        request_source=_source(header["request_filename"], header["request_sha256"]),
        price_source=_source(header["price_filename"], header["price_sha256"]),
        selected_count=header["selected_count"],
        excluded_count=header["excluded_count"],
        calculation_complete=bool(header["calculation_complete"]),
        missing_buyer_fields=missing,
        buyer=_party(header, "buyer_", Buyer),
    )


def _quote_row(
    document: SavedQuote,
    summary: QuoteSummary,
    pdf: bytes,
    idempotency_key: str | None,
) -> dict[str, object]:
    """Разложить заголовок документа по столбцам.

    Args:
        document: Снимок.
        summary: Строка истории.
        pdf: Байты PDF.
        idempotency_key: Ключ повтора. Пусто у документов из старой базы.

    Returns:
        Параметры вставки.
    """
    quote = document.quote
    row: dict[str, object] = {
        "id": document.id,
        "number": document.number,
        "created_at": document.created_at,
        "idempotency_key": idempotency_key,
        "filename": summary.filename,
        "pdf": pdf,
        "request_id": quote.request_id,
        "discount_bp": basis_points(quote.discount_percent),
        "vat_bp": basis_points(quote.vat_rate),
        "currency": quote.currency,
        "confirmed_count": quote.confirmed_count,
        "unresolved_count": quote.unresolved_count,
        "is_complete": _bit(quote.is_complete),
        "subtotal_kopecks": kopecks(quote.subtotal_with_vat),
        "vat_kopecks": kopecks(quote.vat_amount),
        "selected_count": quote.selected_count,
        "excluded_count": quote.excluded_count,
        "calculation_complete": _bit(quote.calculation_complete),
        "buyer_name": summary.buyer_name,
    }
    row.update(_source_columns("request", quote.request_source))
    row.update(_source_columns("price", quote.price_source))
    row.update(_prefixed(document.seller, "seller_", _SELLER))
    row.update(_prefixed(quote.buyer, "buyer_", _BUYER))
    return row


def _insert_lines(connection: sqlite3.Connection, document: SavedQuote) -> None:
    """Записать строки, кандидатов и пропущенные поля покупателя.

    Args:
        connection: Открытая транзакция.
        document: Снимок.
    """
    for position, line in enumerate(document.quote.lines):
        insert(connection, "quote_lines", _line_row(document.id, position, line))
        _insert_candidates(connection, document.id, position, line.candidates)
    for field in document.quote.missing_buyer_fields:
        insert(
            connection,
            "quote_missing_fields",
            {"quote_id": document.id, "field": field},
        )


def _insert_candidates(
    connection: sqlite3.Connection,
    quote_id: str,
    position: int,
    candidates: tuple[Product, ...],
) -> None:
    """Записать товары, из которых можно было выбрать.

    Args:
        connection: Открытая транзакция.
        quote_id: Документ.
        position: Номер строки.
        candidates: Кандидаты.
    """
    for index, product in enumerate(candidates):
        row = _product_columns(product)
        row["quote_id"] = quote_id
        row["position"] = position
        row["candidate_index"] = index
        insert(connection, "quote_candidates", row)


def _line_row(quote_id: str, position: int, line: QuoteLine) -> dict[str, object]:
    """Разложить строку расчёта.

    Args:
        quote_id: Документ.
        position: Порядок строки.
        line: Строка расчёта.

    Returns:
        Параметры вставки.
    """
    row: dict[str, object] = {
        "quote_id": quote_id,
        "position": position,
        "request_id": line.request.request_id,
        "line": line.request.line,
        "sku": line.request.sku,
        "name": line.request.name,
        "quantity": line.request.quantity,
        "unit": line.request.unit,
        "status": line.status.value,
        "sale_quantity": line.sale_quantity,
        "discounted_kopecks": kopecks(line.discounted_price),
        "unit_kopecks": kopecks(line.unit_price_with_vat),
        "total_kopecks": kopecks(line.total_with_vat),
        "vat_kopecks": kopecks(line.vat_amount),
        "note": line.note,
        "manually_selected": _bit(line.manually_selected),
    }
    row.update(_selected_columns(line.selected))
    return row


def _line(row: sqlite3.Row, candidates: tuple[Product, ...]) -> QuoteLine:
    """Собрать строку расчёта.

    Args:
        row: Строка таблицы.
        candidates: Кандидаты этой строки.

    Returns:
        Строка расчёта.
    """
    return QuoteLine(
        request=RequestRow(
            request_id=row["request_id"],
            line=row["line"],
            sku=row["sku"],
            name=row["name"],
            quantity=row["quantity"],
            unit=row["unit"],
        ),
        status=Status(row["status"]),
        selected=_selected(row),
        sale_quantity=row["sale_quantity"],
        discounted_price=from_kopecks(row["discounted_kopecks"]),
        unit_price_with_vat=from_kopecks(row["unit_kopecks"]),
        total_with_vat=from_kopecks(row["total_kopecks"]),
        vat_amount=from_kopecks(row["vat_kopecks"]),
        candidates=candidates,
        note=row["note"],
        manually_selected=bool(row["manually_selected"]),
    )


def _candidates(
    connection: sqlite3.Connection, quote_id: str
) -> dict[int, list[Product]]:
    """Сгруппировать кандидатов по номеру строки.

    Args:
        connection: Открытая транзакция.
        quote_id: Документ.

    Returns:
        Кандидаты по позиции.
    """
    grouped: dict[int, list[Product]] = {}
    rows = connection.execute(
        "SELECT * FROM quote_candidates WHERE quote_id = ? "
        "ORDER BY position, candidate_index",
        (quote_id,),
    )
    for row in rows:
        grouped.setdefault(int(row["position"]), []).append(_candidate(row))
    return grouped


def _summary(row: sqlite3.Row) -> QuoteSummary:
    """Собрать строку истории.

    Args:
        row: Выборка кратких столбцов.

    Returns:
        Строка истории.
    """
    return QuoteSummary(
        id=row["id"],
        number=row["number"],
        created_at=row["created_at"],
        request_id=row["request_id"],
        buyer_name=row["buyer_name"],
        subtotal_with_vat=money_required(int(row["subtotal_kopecks"])),
        vat_amount=money_required(int(row["vat_kopecks"])),
        is_complete=bool(row["is_complete"]),
        selected_count=row["selected_count"],
        unresolved_count=row["unresolved_count"],
        filename=row["filename"],
    )


def _selected(row: sqlite3.Row) -> Product | None:
    """Собрать подтверждённый товар строки, если он был.

    Args:
        row: Строка расчёта.

    Returns:
        Товар или ``None``.
    """
    if row["selected_id"] is None:
        return None
    return Product.model_validate(
        {
            "id": row["selected_id"],
            "sku": row["selected_sku"],
            "name": row["selected_name"],
            "unit": row["selected_unit"],
            "pack_size": row["selected_pack_size"],
            "price": from_kopecks(row["selected_price_kopecks"]),
            "price_basis": row["selected_price_basis"],
            "vat_rate": from_basis_points(int(row["selected_vat_bp"])),
            "source": row["selected_source"],
            "updated_at": row["selected_updated_at"],
        }
    )


def _selected_columns(product: Product | None) -> dict[str, object]:
    """Разложить подтверждённый товар или записать пустые столбцы.

    Args:
        product: Товар строки.

    Returns:
        Столбцы с префиксом ``selected_``.
    """
    if product is None:
        return {f"selected_{name}": None for name in _product_names()}
    return {
        f"selected_{name}": value for name, value in _product_columns(product).items()
    }


def _candidate(row: sqlite3.Row) -> Product:
    """Собрать кандидата.

    Args:
        row: Строка кандидата.

    Returns:
        Товар.
    """
    return Product.model_validate(
        {
            "id": row["id"],
            "sku": row["sku"],
            "name": row["name"],
            "unit": row["unit"],
            "pack_size": row["pack_size"],
            "price": from_kopecks(row["price_kopecks"]),
            "price_basis": row["price_basis"],
            "vat_rate": from_basis_points(int(row["vat_bp"])),
            "source": row["source"],
            "updated_at": row["updated_at"],
        }
    )


def _product_columns(product: Product) -> dict[str, object]:
    """Разложить товар кандидата.

    Args:
        product: Товар.

    Returns:
        Столбцы без префикса.
    """
    return {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "unit": product.unit,
        "pack_size": product.pack_size,
        "price_kopecks": kopecks(product.price),
        "price_basis": product.price_basis,
        "vat_bp": basis_points(product.vat_rate),
        "source": product.source,
        "updated_at": product.updated_at,
    }


def _product_names() -> tuple[str, ...]:
    """Имена столбцов товара.

    Returns:
        Имена без префикса.
    """
    return (
        "id",
        "sku",
        "name",
        "unit",
        "pack_size",
        "price_kopecks",
        "price_basis",
        "vat_bp",
        "source",
        "updated_at",
    )


def _seller(row: sqlite3.Row) -> Seller:
    """Собрать продавца снимка.

    Args:
        row: Заголовок документа.

    Returns:
        Продавец.
    """
    return Seller.model_validate({key: row[f"seller_{key}"] for key in _SELLER})


def _party[T: Buyer](row: sqlite3.Row, prefix: str, model: type[T]) -> T:
    """Собрать покупателя снимка.

    Args:
        row: Заголовок документа.
        prefix: Префикс столбцов.
        model: Класс покупателя.

    Returns:
        Покупатель.
    """
    return model.model_validate({key: row[f"{prefix}{key}"] for key in _BUYER})


def _prefixed(
    model: Buyer | Seller, prefix: str, names: tuple[str, ...]
) -> dict[str, str]:
    """Разложить модель по столбцам с префиксом.

    Args:
        model: Покупатель или продавец.
        prefix: Префикс столбца.
        names: Имена полей.

    Returns:
        Пары столбец-значение.
    """
    data = model.model_dump()
    return {f"{prefix}{name}": str(data[name]) for name in names}


def _source(name: object, digest: object) -> SourceFile | None:
    """Собрать источник файла, если оба столбца заполнены.

    Args:
        name: Имя файла.
        digest: Отпечаток.

    Returns:
        Источник или ``None``.
    """
    if name is None or digest is None:
        return None
    return SourceFile(name=str(name), sha256=str(digest))


def _source_columns(prefix: str, source: SourceFile | None) -> dict[str, str | None]:
    """Разложить источник файла.

    Args:
        prefix: ``request`` или ``price``.
        source: Источник либо пусто.

    Returns:
        Имя и отпечаток.
    """
    if source is None:
        return {f"{prefix}_filename": None, f"{prefix}_sha256": None}
    return {f"{prefix}_filename": source.name, f"{prefix}_sha256": source.sha256}


def _bit(value: bool) -> int:
    """Сохранить логическое значение числом 0 или 1.

    Args:
        value: Признак.

    Returns:
        1 или 0.
    """
    if value:
        return 1
    return 0
