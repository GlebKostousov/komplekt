"""Проверить перенос старой базы, повтор выпуска и черновик формы."""

import csv
import sqlite3
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.documents import default_seller, render_pdf
from app.domain import (
    Buyer,
    Catalog,
    Product,
    QuoteSummary,
    RequestRecord,
    RequestRow,
    SavedQuote,
    State,
    build_draft,
)

DATA = Path(__file__).resolve().parents[1] / "data"
HEADERS = {"X-Komplekt-Request": "1"}
NOW = "2026-10-27T12:00:00+00:00"
OLD_DDL = """
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO metadata (key, value) VALUES ('revision', '4');
CREATE TABLE products (
    id TEXT PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE requests (request_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE quotes (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT UNIQUE NOT NULL,
    data TEXT NOT NULL,
    summary TEXT NOT NULL,
    pdf BLOB NOT NULL
);
CREATE TABLE pending_imports (
    token TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    payload BLOB NOT NULL,
    revision INTEGER NOT NULL,
    expires_at TEXT NOT NULL
);
"""


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """Открыть отдельную базу для проверки повторных действий."""
    database = tmp_path / "app.sqlite3"
    with TestClient(create_app(database_path=database), headers=HEADERS) as opened:
        yield opened


def test_legacy_rows_keep_numbers_and_drafts(tmp_path: Path) -> None:
    """Старые JSON-записи становятся столбцами и не теряют номер документа."""
    path = tmp_path / "legacy.sqlite3"
    pdf = _write_legacy(path)
    with TestClient(create_app(database_path=path), headers=HEADERS) as opened:
        state = _state(opened)
        assert state.revision == 4
        assert state.requests[0].discount_percent == Decimal("15")
        assert state.requests[0].discount_draft == "15"
        assert state.requests[0].buyer_draft.inn == state.requests[0].buyer.inn
        assert state.quotes[0].number == "0007"
        assert opened.get(f"/api/quotes/{state.quotes[0].id}/pdf").content == pdf
        created = opened.post(
            "/api/quotes",
            headers={"Idempotency-Key": uuid4().hex},
            json={
                "revision": state.revision,
                "request_id": "REQ-001",
                "allow_incomplete": True,
            },
        )
        assert created.status_code == 200, created.text
    with TestClient(create_app(database_path=path), headers=HEADERS) as reopened:
        again = _state(reopened)
    assert [item.number for item in again.quotes] == ["0008", "0007"]
    _assert_migrated(path)


def test_same_key_does_not_create_a_second_quote(client: TestClient) -> None:
    """Повтор того же нажатия возвращает первый документ."""
    seeded = _seed(client)
    key = uuid4().hex
    body = {
        "revision": seeded.revision,
        "request_id": "REQ-001",
        "allow_incomplete": True,
    }
    first = client.post("/api/quotes", headers={"Idempotency-Key": key}, json=body)
    second = client.post("/api/quotes", headers={"Idempotency-Key": key}, json=body)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["quote_id"] == second.json()["quote_id"]
    assert len(_state(client).quotes) == 1


def test_missing_quote_key_is_rejected(client: TestClient) -> None:
    """Без ключа повтора документ не создаётся."""
    seeded = _seed(client)
    response = client.post(
        "/api/quotes",
        json={
            "revision": seeded.revision,
            "request_id": "REQ-001",
            "allow_incomplete": True,
        },
    )
    assert response.status_code == 422
    assert _state(client).quotes == ()


def test_unsaved_requisites_survive_reload(client: TestClient) -> None:
    """Незаконченные реквизиты и текст скидки остаются после нового чтения."""
    seeded = _seed(client)
    response = client.patch(
        "/api/requests/REQ-001/draft",
        json={
            "revision": seeded.revision,
            "buyer_draft": {"company_name": "Черновик", "inn": "12"},
            "discount_draft": "7,5",
        },
    )
    assert response.status_code == 200, response.text
    state = _state(client)
    assert state.requests[0].buyer_draft.company_name == "Черновик"
    assert state.requests[0].buyer_draft.inn == "12"
    assert state.requests[0].buyer.inn == ""
    assert state.requests[0].discount_draft == "7,5"
    assert state.requests[0].discount_percent == Decimal("10")


def test_unhandled_failure_is_safe_json(tmp_path: Path) -> None:
    """Непойманный сбой не отдаёт внутренний текст."""
    app = create_app(
        database_path=tmp_path / "boom.sqlite3",
        frontend_path=tmp_path / "no-frontend",
    )

    @app.get("/api/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("secret-token")

    with TestClient(app, raise_server_exceptions=False) as opened:
        response = opened.get("/api/boom")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "secret-token" not in response.text
    assert "Traceback" not in response.text


def _state(client: TestClient) -> State:
    """Прочитать состояние через HTTP."""
    response = client.get("/api/state")
    assert response.status_code == 200, response.text
    return State.model_validate(response.json())


def _seed(client: TestClient) -> State:
    """Загрузить учебные прайс и заявку."""
    _upload(client, "price")
    return _upload(client, "request")


def _upload(client: TestClient, kind: str) -> State:
    """Проверить и подтвердить один учебный файл."""
    checked = client.post(
        f"/api/imports/{kind}/preview",
        files={
            "file": (f"{kind}.csv", (DATA / f"{kind}.csv").read_bytes(), "text/csv"),
        },
    )
    assert checked.status_code == 200, checked.text
    payload = checked.json()
    applied = client.post(
        "/api/imports/commit",
        json={"token": payload["token"], "revision": payload["revision"]},
    )
    assert applied.status_code == 200, applied.text
    return State.model_validate(applied.json())


def _write_legacy(path: Path) -> bytes:
    """Собрать базу в прежнем формате и вернуть байты её PDF."""
    request = _legacy_request()
    catalog = _legacy_catalog()
    document = SavedQuote(
        id="b" * 32,
        number="0007",
        created_at=NOW,
        seller=default_seller(),
        quote=build_draft(request, catalog),
    )
    pdf = render_pdf(document)
    summary = _summary(document)
    connection = sqlite3.connect(path)
    connection.executescript(OLD_DDL)
    _insert_legacy(connection, catalog, request, document, summary, pdf)
    connection.commit()
    connection.close()
    return pdf


def _insert_legacy(
    connection: sqlite3.Connection,
    catalog: Catalog,
    request: RequestRecord,
    document: SavedQuote,
    summary: QuoteSummary,
    pdf: bytes,
) -> None:
    """Положить JSON туда, где его ждала старая схема."""
    info = catalog.model_copy(update={"products": ()})
    connection.execute(
        "INSERT INTO metadata (key, value) VALUES ('catalog', ?)",
        (info.model_dump_json(),),
    )
    connection.executemany(
        "INSERT INTO products (id, sku, data) VALUES (?, ?, ?)",
        [(item.id, item.sku, item.model_dump_json()) for item in catalog.products],
    )
    connection.execute(
        "INSERT INTO requests (request_id, data) VALUES (?, ?)",
        (request.request_id, request.model_dump_json()),
    )
    connection.execute(
        "INSERT INTO quotes (sequence, id, data, summary, pdf) VALUES (7, ?, ?, ?, ?)",
        (document.id, document.model_dump_json(), summary.model_dump_json(), pdf),
    )
    connection.execute(
        "INSERT INTO pending_imports VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("c" * 32, "price", "price.csv", "text/csv", b"a", 4, NOW),
    )


def _legacy_request() -> RequestRecord:
    """Собрать заявку со скидкой, отличной от значения по умолчанию."""
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
        buyer=Buyer(
            company_name="ООО Покупатель Демо",
            inn="9900000000",
            address="Учебный адрес",
        ),
        selected_lines=tuple(row.line for row in rows),
        discount_percent=Decimal("15"),
    )


def _legacy_catalog() -> Catalog:
    """Собрать прайс с идентификаторами новой длины."""
    with (DATA / "price.csv").open(encoding="utf-8-sig") as stream:
        products = tuple(
            Product.model_validate(value | {"id": uuid4().hex, "updated_at": NOW})
            for value in csv.DictReader(stream, delimiter=";")
        )
    return Catalog(
        generation="a" * 32,
        filename="price.csv",
        sha256="0" * 64,
        uploaded_at=NOW,
        products=products,
    )


def _summary(document: SavedQuote) -> QuoteSummary:
    """Собрать строку истории так же, как при выпуске."""
    quote = document.quote
    return QuoteSummary(
        id=document.id,
        number=document.number,
        created_at=document.created_at,
        request_id=quote.request_id,
        buyer_name=quote.buyer.company_name or "Не указан",
        subtotal_with_vat=quote.subtotal_with_vat,
        vat_amount=quote.vat_amount,
        is_complete=quote.is_complete,
        selected_count=quote.selected_count,
        unresolved_count=quote.unresolved_count,
        filename=f"KP-{document.number}-{quote.request_id}.pdf",
    )


def _assert_migrated(path: Path) -> None:
    """Убедиться, что версия схемы записана, а служебная загрузка сохранена."""
    connection = sqlite3.connect(path)
    version = connection.execute(
        "SELECT MAX(version) FROM schema_migrations"
    ).fetchone()
    pending = connection.execute("SELECT COUNT(*) FROM pending_imports").fetchone()
    columns = connection.execute("PRAGMA table_info(products)").fetchall()
    connection.close()
    assert version is not None and version[0] == 1
    assert pending is not None and pending[0] == 1
    assert "data" not in {column[1] for column in columns}
