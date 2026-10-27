"""Чтение и запись прайса и заявок по столбцам."""

import sqlite3

from app.domain import (
    Buyer,
    BuyerDraft,
    Catalog,
    Product,
    RequestRecord,
    RequestRow,
)

from ._errors import NotFoundError
from ._money import basis_points, from_basis_points, from_kopecks, kopecks
from ._sql import insert, upsert

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


def load_catalog(connection: sqlite3.Connection) -> Catalog | None:
    """Собрать текущий прайс из строки каталога и товаров.

    Args:
        connection: Открытая транзакция.

    Returns:
        Каталог или ``None``, если прайс ещё не загружали.
    """
    row = connection.execute("SELECT * FROM catalog WHERE id = 1").fetchone()
    if row is None:
        return None
    products = tuple(
        _product(item)
        for item in connection.execute("SELECT * FROM products ORDER BY sku")
    )
    return Catalog(
        generation=row["generation"],
        filename=row["filename"],
        uploaded_at=row["uploaded_at"],
        sha256=row["sha256"],
        products=products,
    )


def replace_catalog(connection: sqlite3.Connection, catalog: Catalog) -> None:
    """Заменить товары и снять прежние ручные соответствия.

    Args:
        connection: Открытая транзакция.
        catalog: Новый прайс.
    """
    connection.execute("DELETE FROM request_choices")
    connection.execute("DELETE FROM products")
    for product in catalog.products:
        insert(connection, "products", _product_row(product))
    upsert(
        connection,
        "catalog",
        {
            "id": 1,
            "generation": catalog.generation,
            "filename": catalog.filename,
            "uploaded_at": catalog.uploaded_at,
            "sha256": catalog.sha256,
        },
        "id",
    )
    for request in load_requests(connection):
        save_request(connection, request.model_copy(update={"choices": {}}))


def load_product(connection: sqlite3.Connection, product_id: str) -> Product:
    """Найти товар текущего прайса.

    Args:
        connection: Открытая транзакция.
        product_id: Идентификатор сущности.

    Returns:
        Товар.

    Raises:
        NotFoundError: Товара нет в текущем прайсе.
    """
    row = connection.execute(
        "SELECT * FROM products WHERE id = ?", (product_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("Этого товара уже нет в текущем прайсе. Обновите страницу.")
    return _product(row)


def save_product(connection: sqlite3.Connection, product: Product) -> None:
    """Обновить столбцы одного товара.

    Args:
        connection: Открытая транзакция.
        product: Товар с новой ценой.
    """
    upsert(connection, "products", _product_row(product), "id")


def load_requests(connection: sqlite3.Connection) -> tuple[RequestRecord, ...]:
    """Прочитать заявки, последняя сохранённая строка заголовка идёт первой.

    Args:
        connection: Открытая транзакция.

    Returns:
        Заявки.
    """
    rows = connection.execute("SELECT request_id FROM requests ORDER BY rowid DESC")
    return tuple(_request(connection, row["request_id"]) for row in rows)


def find_request(
    connection: sqlite3.Connection, request_id: str
) -> RequestRecord | None:
    """Найти заявку по номеру.

    Args:
        connection: Открытая транзакция.
        request_id: Номер заявки.

    Returns:
        Заявка или ``None``.
    """
    row = connection.execute(
        "SELECT request_id FROM requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    if row is None:
        return None
    return _request(connection, request_id)


def save_request(connection: sqlite3.Connection, request: RequestRecord) -> None:
    """Записать заголовок заявки и заново её строки.

    Args:
        connection: Открытая транзакция.
        request: Заявка целиком.
    """
    upsert(connection, "requests", _request_row(request), "request_id")
    connection.execute(
        "DELETE FROM request_lines WHERE request_id = ?", (request.request_id,)
    )
    _insert_lines(connection, request)


def _request(connection: sqlite3.Connection, request_id: str) -> RequestRecord:
    """Собрать заявку из заголовка и дочерних строк.

    Args:
        connection: Открытая транзакция.
        request_id: Номер заявки.

    Returns:
        Заявка.
    """
    header = connection.execute(
        "SELECT * FROM requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    lines = connection.execute(
        "SELECT * FROM request_lines WHERE request_id = ? ORDER BY line",
        (request_id,),
    ).fetchall()
    selected = {
        row["line"]
        for row in connection.execute(
            "SELECT line FROM request_selected WHERE request_id = ?", (request_id,)
        )
    }
    choices = {
        str(row["line"]): row["product_id"]
        for row in connection.execute(
            "SELECT line, product_id FROM request_choices WHERE request_id = ?",
            (request_id,),
        )
    }
    rows = tuple(_request_line(row) for row in lines)
    return RequestRecord(
        request_id=header["request_id"],
        filename=header["filename"],
        sha256=header["sha256"],
        uploaded_at=header["uploaded_at"],
        rows=rows,
        buyer=_buyer(header, ""),
        buyer_draft=_buyer_draft(header),
        selected_lines=tuple(row.line for row in rows if row.line in selected),
        choices=choices,
        discount_percent=from_basis_points(int(header["discount_bp"])),
        discount_draft=header["discount_draft"],
    )


def _insert_lines(connection: sqlite3.Connection, request: RequestRecord) -> None:
    """Записать строки, выбор и соответствия.

    Args:
        connection: Открытая транзакция.
        request: Заявка.
    """
    for row in request.rows:
        _insert_line(connection, request, row)
    _insert_choices(connection, request)


def _insert_line(
    connection: sqlite3.Connection, request: RequestRecord, row: RequestRow
) -> None:
    """Записать одну строку и отметку выбора.

    Args:
        connection: Открытая транзакция.
        request: Заявка.
        row: Строка заявки.
    """
    insert(
        connection,
        "request_lines",
        {
            "request_id": request.request_id,
            "line": row.line,
            "sku": row.sku,
            "name": row.name,
            "quantity": row.quantity,
            "unit": row.unit,
        },
    )
    if row.line not in request.selected_lines:
        return
    insert(
        connection,
        "request_selected",
        {"request_id": request.request_id, "line": row.line},
    )


def _insert_choices(connection: sqlite3.Connection, request: RequestRecord) -> None:
    """Записать ручные соответствия.

    Args:
        connection: Открытая транзакция.
        request: Заявка.
    """
    for line, product_id in request.choices.items():
        insert(
            connection,
            "request_choices",
            {
                "request_id": request.request_id,
                "line": int(line),
                "product_id": product_id,
            },
        )


def _request_row(request: RequestRecord) -> dict[str, object]:
    """Разложить заявку по столбцам заголовка.

    Args:
        request: Заявка.

    Returns:
        Параметры заголовка.
    """
    row: dict[str, object] = {
        "request_id": request.request_id,
        "filename": request.filename,
        "sha256": request.sha256,
        "uploaded_at": request.uploaded_at,
        "discount_bp": basis_points(request.discount_percent),
        "discount_draft": request.discount_draft,
    }
    row.update(_party(request.buyer, ""))
    row.update(_party(request.buyer_draft, "draft_"))
    return row


def _product(row: sqlite3.Row) -> Product:
    """Собрать товар из столбцов.

    Args:
        row: Строка таблицы товаров.

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


def _product_row(product: Product) -> dict[str, object]:
    """Разложить товар по столбцам.

    Args:
        product: Товар.

    Returns:
        Параметры вставки.
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


def _request_line(row: sqlite3.Row) -> RequestRow:
    """Собрать строку заявки.

    Args:
        row: Строка таблицы позиций.

    Returns:
        Строка заявки.
    """
    return RequestRow(
        request_id=row["request_id"],
        line=row["line"],
        sku=row["sku"],
        name=row["name"],
        quantity=row["quantity"],
        unit=row["unit"],
    )


def _buyer(row: sqlite3.Row, prefix: str) -> Buyer:
    """Собрать проверенного покупателя.

    Args:
        row: Строка заголовка.
        prefix: Префикс столбцов.

    Returns:
        Покупатель.
    """
    return Buyer.model_validate({key: row[f"{prefix}{key}"] for key in _BUYER})


def _buyer_draft(row: sqlite3.Row) -> BuyerDraft:
    """Собрать черновик реквизитов.

    Args:
        row: Строка заголовка.

    Returns:
        Черновик.
    """
    return BuyerDraft.model_validate({key: row[f"draft_{key}"] for key in _BUYER})


def _party(party: Buyer | BuyerDraft, prefix: str) -> dict[str, str]:
    """Разложить реквизиты по столбцам.

    Args:
        party: Покупатель или черновик.
        prefix: Префикс имени столбца.

    Returns:
        Пары столбец-значение.
    """
    data = party.model_dump()
    return {f"{prefix}{key}": str(data[key]) for key in _BUYER}
