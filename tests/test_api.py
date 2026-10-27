"""Проверить пользовательские сценарии через настоящий HTTP-контракт."""

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Literal, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from app import create_app
from app.domain import Draft, Product, State

DATA = Path(__file__).resolve().parents[1] / "data"
REQUEST_URL = "/api/requests/REQ-001"
HEADERS = {"X-Komplekt-Request": "1"}
BUYER = {
    "company_name": "ООО Покупатель Демо",
    "inn": "9901234561",
    "kpp": "990101001",
    "ogrn": "1269900000017",
    "address": "Учебный адрес для проверки",
    "contact_name": "Анна Примерова",
    "email": "demo@example.test",
    "phone": "+7 (812) 555-12-34",
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    """У каждой проверки отдельная настоящая база SQLite."""
    with TestClient(
        create_app(database_path=tmp_path / "app.sqlite3"), headers=HEADERS
    ) as opened:
        yield opened


def current(client: TestClient) -> State:
    """Прочитать состояние тем же способом, что и браузер."""
    response = client.get("/api/state")
    assert response.status_code == 200, response.text
    return State.model_validate(response.json())


def state_response(response: Response) -> State:
    """Требовать успешного изменения с полным новым состоянием."""
    assert response.status_code == 200, response.text
    return State.model_validate(response.json())


def preview(
    client: TestClient, kind: Literal["price", "request"], payload: bytes | None = None
) -> dict[str, object]:
    """Отправить CSV на проверку, ещё не применяя его."""
    content = payload if payload is not None else (DATA / f"{kind}.csv").read_bytes()
    response = client.post(
        f"/api/imports/{kind}/preview",
        files={"file": (f"{kind}.csv", content, "text/csv")},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def commit(client: TestClient, checked: dict[str, object]) -> State:
    """Подтвердить конкретную проверенную загрузку."""
    return state_response(
        client.post(
            "/api/imports/commit",
            json={
                "token": checked["token"],
                "revision": checked["revision"],
            },
        )
    )


def upload(
    client: TestClient, kind: Literal["price", "request"], payload: bytes | None = None
) -> State:
    """Пройти проверку и явное подтверждение загрузки."""
    return commit(client, preview(client, kind, payload))


def seed(client: TestClient) -> State:
    """Загрузить исходные файлы без изменения и получить одну заявку."""
    upload(client, "price")
    return upload(client, "request")


def product(state: State, sku: str) -> Product:
    """Найти текущую сущность по артикулу в проверяемом состоянии."""
    assert state.catalog is not None
    return next(row for row in state.catalog.products if row.sku == sku)


def calculate(client: TestClient) -> Draft:
    """Запросить текущий расчёт, а не использовать сохранённый PDF."""
    response = client.get(REQUEST_URL + "/calculation")
    assert response.status_code == 200, response.text
    return Draft.model_validate(response.json()["quote"])


def edit_price(client: TestClient, sku: str, value: str | None) -> State:
    """Изменить общую цену товара через API."""
    state = current(client)
    identifier = product(state, sku).id
    return state_response(
        client.patch(
            f"/api/products/{identifier}",
            json={
                "revision": state.revision,
                "price": value,
                "source": "Уточнено по учебному прайсу",
            },
        )
    )


def choose_filter(client: TestClient) -> State:
    """Явно выбрать M-20 для третьей строки заявки."""
    state = current(client)
    return state_response(
        client.put(
            REQUEST_URL + "/choices/3",
            json={
                "revision": state.revision,
                "product_id": product(state, "M-20").id,
            },
        )
    )


def save_buyer(client: TestClient) -> State:
    """Сохранить заполненную карточку учебного покупателя."""
    return state_response(
        client.patch(
            REQUEST_URL + "/buyer",
            json={
                "revision": current(client).revision,
                "buyer": BUYER,
            },
        )
    )


def create_document(client: TestClient, allow_incomplete: bool) -> str:
    """Выпустить документ и вернуть его собственный идентификатор."""
    response = client.post(
        "/api/quotes",
        headers={"Idempotency-Key": uuid4().hex},
        json={
            "revision": current(client).revision,
            "request_id": "REQ-001",
            "allow_incomplete": allow_incomplete,
        },
    )
    assert response.status_code == 200, response.text
    identifier = response.json()["quote_id"]
    assert isinstance(identifier, str)
    return identifier


def test_preview_does_not_modify_catalog_or_request(client: TestClient) -> None:
    """Проверка файла сама по себе не заменяет ни одну сохранённую запись."""
    before = current(client)
    checked = preview(client, "price")
    assert checked["row_count"] == 5
    assert len(cast(list[object], checked["warnings"])) == 1
    assert current(client) == before
    applied = commit(client, checked)
    assert applied.catalog is not None and len(applied.catalog.products) == 5
    assert applied.requests == ()
    assert product(applied, "C-300").price is None


def test_failed_import_keeps_every_old_record(client: TestClient) -> None:
    """Неверная строка в конце не допускает частичного обновления прайса."""
    seed(client)
    before = edit_price(client, "A-100", "1111")
    text = (DATA / "price.csv").read_text(encoding="utf-8-sig")
    payload = text.replace(";1000;net;", ";999;net;") + "BROKEN;Недописанная строка\n"
    response = client.post(
        "/api/imports/price/preview",
        files={
            "file": ("price.csv", payload.encode(), "text/csv"),
        },
    )
    assert response.status_code == 422
    assert response.json()["issues"]
    assert current(client) == before
    assert product(current(client), "A-100").price == Decimal("1111")


def test_stale_edits_and_stale_preview_do_not_overwrite(client: TestClient) -> None:
    """Вторая вкладка не может затереть новые данные старой формой."""
    old = seed(client)
    checked = preview(client, "price")
    latest = edit_price(client, "A-100", "1100")
    response = client.patch(
        f"/api/products/{product(old, 'A-100').id}",
        json={
            "revision": old.revision,
            "price": "900",
            "source": "Старая вкладка",
        },
    )
    assert response.status_code == 409
    response = client.post(
        "/api/imports/commit",
        json={
            "token": checked["token"],
            "revision": checked["revision"],
        },
    )
    assert response.status_code == 409
    assert current(client) == latest
    assert calculate(client).subtotal_with_vat == Decimal("3276.00")


def test_replacing_price_recreates_entities_and_preserves_issued_pdf(
    client: TestClient,
) -> None:
    """Замена прайса удаляет старые товары, но не историю документов."""
    seed(client)
    choose_filter(client)
    edit_price(client, "C-300", "777")
    before = current(client)
    identifier = create_document(client, True)
    pdf_before = client.get(f"/api/quotes/{identifier}/pdf").content
    snapshot_before = client.get(f"/api/quotes/{identifier}").json()
    assert pdf_before.startswith(b"%PDF-")
    payload = (
        "sku;name;unit;pack_size;price;price_basis;vat_rate;source\n"
        "A-100;Датчик A;шт;1;1100;net;20;Новый учебный прайс\n"
        "D-400;Датчик D;шт;1;;net;20;Новый учебный прайс\n"
    ).encode()
    checked = preview(client, "price", payload)
    assert checked["changes"] == {
        "added": 1,
        "changed": 1,
        "removed": 4,
        "replaces_request": False,
    }
    after = commit(client, checked)
    assert after.catalog is not None and before.catalog is not None
    assert {row.sku for row in after.catalog.products} == {"A-100", "D-400"}
    assert {row.id for row in before.catalog.products}.isdisjoint(
        row.id for row in after.catalog.products
    )
    assert after.requests[0].choices == {}
    assert len(after.quotes) == 1
    assert client.get(f"/api/quotes/{identifier}/pdf").content == pdf_before
    assert client.get(f"/api/quotes/{identifier}").json() == snapshot_before
    assert calculate(client).subtotal_with_vat == Decimal("2376.00")


def test_repeating_request_updates_one_record_and_preserves_buyer(
    client: TestClient,
) -> None:
    """Тот же файл не создаёт заказ заново; изменённый сбрасывает подбор."""
    seed(client)
    save_buyer(client)
    before = choose_filter(client)
    repeated = upload(client, "request")
    assert len(repeated.requests) == 1
    assert repeated.requests[0].buyer == before.requests[0].buyer
    assert repeated.requests[0].choices == before.requests[0].choices
    text = (DATA / "request.csv").read_text(encoding="utf-8-sig")
    changed = upload(
        client, "request", text.replace(";Датчик A;2;", ";Датчик A;3;").encode()
    )
    assert len(changed.requests) == 1
    assert changed.requests[0].rows[0].quantity == 3
    assert changed.requests[0].buyer == before.requests[0].buyer
    assert changed.requests[0].choices == {}
    assert changed.requests[0].selected_lines == (1, 2, 3, 4, 5)


def test_incomplete_document_requires_confirmation_and_pdf_stays_fixed(
    client: TestClient,
) -> None:
    """Неполное КП нельзя выпустить незаметно, а выпущенный PDF не пересчитывается."""
    before = seed(client)
    blocked = client.post(
        "/api/quotes",
        headers={"Idempotency-Key": uuid4().hex},
        json={
            "revision": before.revision,
            "request_id": "REQ-001",
            "allow_incomplete": False,
        },
    )
    assert blocked.status_code == 422
    assert current(client) == before
    identifier = create_document(client, True)
    quote = current(client).quotes[0]
    assert not quote.is_complete
    assert quote.subtotal_with_vat == Decimal("3060.00")
    assert quote.vat_amount == Decimal("510.00")
    response = client.get(f"/api/quotes/{identifier}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    edit_price(client, "A-100", "1100")
    assert client.get(f"/api/quotes/{identifier}/pdf").content == response.content
    assert calculate(client).subtotal_with_vat == Decimal("3276.00")


def test_selected_rows_and_valid_buyer_produce_complete_document(
    client: TestClient,
) -> None:
    """Явно выбранные две подтверждённые строки дают готовое КП покупателю."""
    seed(client)
    saved = save_buyer(client)
    selection = client.put(
        REQUEST_URL + "/selection",
        json={
            "revision": saved.revision,
            "lines": [1, 2],
        },
    )
    assert selection.status_code == 200
    draft = calculate(client)
    assert draft.is_complete and draft.excluded_count == 3
    identifier = create_document(client, False)
    assert current(client).quotes[0].is_complete
    snapshot = client.get(f"/api/quotes/{identifier}").json()
    assert snapshot["quote"]["buyer"]["inn"] == BUYER["inn"]
    assert len(snapshot["quote"]["lines"]) == 2


@pytest.mark.parametrize("lines", [[1, 1], [99], [True]])
def test_bad_selection_is_rejected_without_changes(
    client: TestClient, lines: list[int]
) -> None:
    """Нельзя включить чужую, повторную или логическую вместо числовой строку."""
    before = seed(client)
    response = client.put(
        REQUEST_URL + "/selection",
        json={
            "revision": before.revision,
            "lines": lines,
        },
    )
    assert response.status_code == 422
    assert current(client) == before


def test_empty_selection_cannot_be_issued_even_as_draft(client: TestClient) -> None:
    """Подтверждение неполноты не разрешает выгрузить пустой документ."""
    before = seed(client)
    cleared = state_response(
        client.put(
            REQUEST_URL + "/selection",
            json={
                "revision": before.revision,
                "lines": [],
            },
        )
    )
    response = client.post(
        "/api/quotes",
        headers={"Idempotency-Key": uuid4().hex},
        json={
            "revision": cleared.revision,
            "request_id": "REQ-001",
            "allow_incomplete": True,
        },
    )
    assert response.status_code == 422
    assert current(client).quotes == ()


def test_buyer_is_validated_by_server(client: TestClient) -> None:
    """Обход браузерной формы не позволяет сохранить неверный ИНН."""
    before = seed(client)
    response = client.patch(
        REQUEST_URL + "/buyer",
        json={
            "revision": before.revision,
            "buyer": {**BUYER, "inn": "9901234560"},
        },
    )
    assert response.status_code == 422
    assert response.json()["issues"]
    assert "ИНН" in response.text
    assert "Traceback" not in response.text
    assert current(client) == before


def test_null_price_and_explicit_zero_are_global_and_distinct(
    client: TestClient,
) -> None:
    """Ручная цена меняет товар во всех расчётах, а удалённая остаётся пустой."""
    seed(client)
    second_request = (DATA / "request.csv").read_bytes().replace(b"REQ-001", b"REQ-002")
    upload(client, "request", second_request)
    changed = edit_price(client, "C-300", "500,50")
    assert product(changed, "C-300").price == Decimal("500.50")
    assert calculate(client).lines[3].total_with_vat == Decimal("540.54")
    other_response = client.get("/api/requests/REQ-002/calculation")
    other = Draft.model_validate(other_response.json()["quote"])
    assert other.lines[3].total_with_vat == Decimal("540.54")
    changed = edit_price(client, "C-300", "0")
    assert product(changed, "C-300").price == Decimal("0")
    assert calculate(client).lines[3].total_with_vat == Decimal("0.00")
    cleared = edit_price(client, "C-300", None)
    assert product(cleared, "C-300").price is None
    assert calculate(client).lines[3].total_with_vat is None


@pytest.mark.parametrize(
    ("filename", "content", "mime", "status"),
    [
        ("price.pdf", b"%PDF-1.7", "application/pdf", 422),
        ("price.csv", b"PK\x03\x04" + b"a" * 50, "text/csv", 422),
        ("price.csv", b"a" * 1_048_577, "text/csv", 422),
        ("price.csv", b"\x00notcsv", "text/csv", 422),
    ],
    ids=["pdf", "zip", "oversize", "nul"],
)
def test_file_content_checked_at_api_boundary(
    client: TestClient, filename: str, content: bytes, mime: str, status: int
) -> None:
    """Входной HTTP-маршрут не принимает документ под видом CSV."""
    before = seed(client)
    response = client.post(
        "/api/imports/price/preview",
        files={
            "file": (filename, content, mime),
        },
    )
    assert response.status_code == status, response.text
    assert current(client) == before


def test_data_and_saved_pdf_survive_restart(tmp_path: Path) -> None:
    """После закрытия приложения сохранённые данные доступны новой сессии."""
    path = tmp_path / "persistent.sqlite3"
    with TestClient(create_app(database_path=path), headers=HEADERS) as first:
        seed(first)
        save_buyer(first)
        identifier = create_document(first, True)
        before = current(first)
        pdf = first.get(f"/api/quotes/{identifier}/pdf").content
    with TestClient(create_app(database_path=path), headers=HEADERS) as reopened:
        assert current(reopened) == before
        assert reopened.get(f"/api/quotes/{identifier}/pdf").content == pdf
