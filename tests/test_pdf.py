"""Проверить переносы, отсутствующие суммы и буквальный вывод текста в PDF."""

import csv
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.documents import default_seller, render_pdf
from app.domain import (
    Buyer,
    Catalog,
    Product,
    RequestRecord,
    RequestRow,
    SavedQuote,
    build_draft,
)

NOW = "2026-10-27T12:00:00+03:00"
DATA = Path(__file__).resolve().parents[1] / "data"


def _buyer() -> Buyer:
    return Buyer(
        company_name="ООО «Северный цех Демо»",
        inn="9900000000",
        address="г. Санкт-Петербург, пр. Тестовый, д. 5",
    )


def _request() -> RequestRecord:
    with (DATA / "request.csv").open(encoding="utf-8-sig") as stream:
        rows = tuple(
            RequestRow.model_validate(value)
            for value in csv.DictReader(stream, delimiter=";")
        )
    return RequestRecord(
        request_id="REQ-001",
        filename="request.csv",
        sha256="1" * 64,
        uploaded_at=NOW,
        rows=rows,
        selected_lines=tuple(row.line for row in rows),
        buyer=_buyer(),
    )


def _catalog() -> Catalog:
    with (DATA / "price.csv").open(encoding="utf-8-sig") as stream:
        products = tuple(
            Product.model_validate(value | {"id": str(index), "updated_at": NOW})
            for index, value in enumerate(csv.DictReader(stream, delimiter=";"))
        )
    return Catalog(
        generation="demo",
        filename="price.csv",
        sha256="0" * 64,
        uploaded_at=NOW,
        products=products,
    )


def _saved(request: RequestRecord, catalog: Catalog | None) -> SavedQuote:
    return SavedQuote(
        id="demo",
        number="КП-20261027-0001",
        created_at=NOW,
        seller=default_seller(),
        quote=build_draft(request, catalog),
    )


def _text(saved: SavedQuote) -> str:
    reader = PdfReader(BytesIO(render_pdf(saved)))
    return "\n".join(page.extract_text() for page in reader.pages)


def test_partial_quote_keeps_all_rows_and_correct_subtotal() -> None:
    output = _text(_saved(_request(), _catalog()))
    assert "Черновик. Не все позиции рассчитаны." in output
    assert "Подытог рассчитанных позиций" in output
    assert "3 060,00" in output
    assert "510,00" in output
    assert "2 упак." in output
    assert "20 шт." in output
    assert "Фильтр М" in output
    assert "Клапан C" in output
    assert "Прибор X" in output
    assert "Цена не указана" in output
    assert "Товара нет в прайсе" in output
    assert "Учебный образец. Компания и реквизиты вымышлены." in output


def test_no_confirmed_rows_are_not_a_zero_offer() -> None:
    output = _text(_saved(_request(), None))
    assert "Не рассчитан" in output
    assert "0,00" not in output


def test_explicit_zero_price_is_visible() -> None:
    catalog = _catalog()
    product = catalog.products[0].model_copy(update={"price": Decimal("0")})
    catalog = catalog.model_copy(update={"products": (product,)})
    request = _request().model_copy(update={"selected_lines": (1,)})
    output = _text(_saved(request, catalog))
    assert "0,00" in output
    assert "Цена не указана" not in output
    assert "Итого по выбранным позициям" in output


def test_buyer_markup_is_printed_as_plain_text() -> None:
    buyer = _buyer().model_copy(update={"company_name": "<b>Покупатель & партнёры</b>"})
    request = _request().model_copy(update={"buyer": buyer})
    output = _text(_saved(request, _catalog()))
    assert "<b>Покупатель & партнёры</b>" in output


def test_two_hundred_rows_repeat_headers_without_losing_items() -> None:
    template = _catalog().products[0]
    products = tuple(
        template.model_copy(
            update={
                "id": f"item-{index}",
                "sku": f"P-{index:03}",
                "name": f"Контрольная позиция {index:03}",
            }
        )
        for index in range(1, 201)
    )
    rows = tuple(
        RequestRow(
            request_id="REQ-001",
            line=index,
            sku=product.sku,
            name=product.name,
            quantity=2,
            unit="шт",
        )
        for index, product in enumerate(products, 1)
    )
    request = _request().model_copy(
        update={"rows": rows, "selected_lines": tuple(range(1, 201))}
    )
    catalog = _catalog().model_copy(update={"products": products})
    reader = PdfReader(BytesIO(render_pdf(_saved(request, catalog))))
    pages = [page.extract_text() for page in reader.pages]
    combined = "\n".join(pages)
    assert len(pages) > 2
    assert all(f"Контрольная позиция {index:03}" in combined for index in range(1, 201))
    assert all(
        "Наименование / артикул" in value
        for value in pages
        if "Контрольная позиция" in value
    )
    assert all("Учебный образец" in value for value in pages)


def test_pdf_date_uses_moscow_timezone() -> None:
    saved = _saved(_request(), _catalog()).model_copy(
        update={"created_at": "2026-10-27T22:00:00+00:00"}
    )
    assert "от 28.10.2026" in _text(saved)
