"""Проверить повреждённые файлы, отсутствующие цены и реквизиты на входе."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain import Buyer, PriceRow, RequestRow
from app.imports import ImportErrorInfo, ParsedUpload, parse_upload

DATA = Path(__file__).resolve().parents[1] / "data"
HEADER = "sku;name;unit;pack_size;price;price_basis;vat_rate;source\n"
REQUEST_HEADER = "request_id;line;sku;name;quantity;unit\n"


def price_csv(line: str) -> ParsedUpload:
    """Прочитать одну строку прайса стандартным публичным входом."""
    return parse_upload(
        "price", (HEADER + line + "\n").encode(), "price.csv", "text/csv"
    )


@pytest.mark.parametrize("price", ["1000,50", "1000.50"])
def test_decimal_comma_and_dot(price: str) -> None:
    """Разрешить два привычных способа записи дробной цены."""
    row = price_csv(f"A-100;Датчик;шт;1;{price};net;20;Прайс").rows[0]
    assert isinstance(row, PriceRow)
    assert row.price == Decimal("1000.50")


def test_empty_is_not_zero_and_warning_points_to_cell() -> None:
    """Отсутствующая цена проходит импорт и получает отдельное замечание."""
    upload = price_csv("C-300;Клапан;шт;1;;net;20;Прайс")
    row = upload.rows[0]
    assert isinstance(row, PriceRow) and row.price is None
    assert upload.warnings[0].row == 2
    assert upload.warnings[0].field == "price"
    zero = price_csv("C-300;Клапан;шт;1;0;net;20;Прайс").rows[0]
    assert isinstance(zero, PriceRow) and zero.price == Decimal("0")


@pytest.mark.parametrize(
    "price",
    ["-1", "NaN", "Infinity", "1e3", "0.001", "100 ₽", "1 000", "1000000000000"],
)
def test_malformed_or_oversized_money_rejected(price: str) -> None:
    """Нельзя принять нечисло, отрицательную цену или лишнюю точность."""
    with pytest.raises(ImportErrorInfo) as caught:
        price_csv(f"A-100;Датчик;шт;1;{price};net;20;Прайс")
    assert caught.value.issues[0].field == "price"
    assert caught.value.issues[0].row == 2


def test_multiple_errors_are_returned_with_locations() -> None:
    """Показать ошибки разных строк за одну проверку."""
    text = REQUEST_HEADER + "R-1;1;A;Датчик;две;шт\nR-1;2;B;Крепёж;0;шт\n"
    with pytest.raises(ImportErrorInfo) as caught:
        parse_upload("request", text.encode(), "request.csv", "text/csv")
    assert [(item.row, item.field) for item in caught.value.issues] == [
        (2, "quantity"),
        (3, "quantity"),
    ]
    assert "целое" in caught.value.issues[0].message
    assert "две" == caught.value.issues[0].value


@pytest.mark.parametrize(
    ("filename", "payload", "mime"),
    [
        ("price.xlsx", b"PK\x03\x04", "application/octet-stream"),
        ("price.csv", b"%PDF-1.7", "text/csv"),
        ("price.csv", b"\x89PNG\r\n", "text/csv"),
        ("price.csv", b"\x00header", "text/csv"),
        ("price.csv", b"hello", "image/png"),
        ("../price.csv", b"hello", "text/csv"),
        ("price.csv.exe", b"hello", "text/csv"),
        ("price\u202e.csv", b"hello", "text/csv"),
        ("price.csv", b"", "text/csv"),
        ("price.csv", b"a" * 1_048_577, "text/csv"),
        ("price.csv", "цена".encode("cp1251"), "text/csv"),
    ],
    ids=[
        "xlsx",
        "pdf",
        "png",
        "nul",
        "image",
        "traversal",
        "double-ext",
        "rtl",
        "empty",
        "oversize",
        "cp1251",
    ],
)
def test_wrong_file_is_rejected(filename: str, payload: bytes, mime: str) -> None:
    """Проверять не только расширение: также тип, байты, размер и кодировку."""
    with pytest.raises(ImportErrorInfo):
        parse_upload("price", payload, filename, mime)


def test_bom_and_quoted_semicolon_are_supported() -> None:
    """Обработать CSV из Excel и точку с запятой внутри названия."""
    text = HEADER + 'A-1;"Датчик; 2 канала";шт;1;100;net;20;Прайс\n'
    result = parse_upload(
        "price", text.encode("utf-8-sig"), "price.CSV", "application/vnd.ms-excel"
    )
    assert result.rows[0].name == "Датчик; 2 канала"


@pytest.mark.parametrize(
    "text",
    [
        "sku,not,a,semicolon\n",
        "sku;sku;unit;pack_size;price;price_basis;vat_rate;source\n",
        HEADER + 'A;"Незакрытое имя;шт;1;100;net;20;Прайс\n',
        HEADER + "A;Датчик;шт;1;100;net;20;Прайс;лишняя ячейка\n",
        HEADER,
        HEADER + "A;Датчик;шт;1;100;net;20;Прайс\nA;Датчик;шт;1;200;net;20;Прайс\n",
        HEADER + "A;Датчик;шт;10;100;net;20;Прайс\n",
        HEADER + "A;Датчик;шт;1;100;net;22;Прайс\n",
        HEADER + "A;Датчик\u200b;шт;1;100;net;20;Прайс\n",
    ],
)
def test_broken_table_and_inconsistent_rows_rejected(text: str) -> None:
    """Не применять повреждённый файл или конфликтующие товары частично."""
    with pytest.raises(ImportErrorInfo):
        parse_upload("price", text.encode(), "price.csv", "text/csv")


def test_mixed_request_ids_and_duplicate_lines_rejected() -> None:
    """Один файл содержит одну заявку без повторяющихся номеров строк."""
    for second in ("R-2;2;B;Крепёж;2;шт", "R-1;1;B;Крепёж;2;шт"):
        text = REQUEST_HEADER + "R-1;1;A;Датчик;2;шт\n" + second
        with pytest.raises(ImportErrorInfo):
            parse_upload("request", text.encode(), "request.csv", "text/csv")


def test_request_row_limit() -> None:
    """Отклонить файл за согласованным пределом 200 позиций."""
    text = REQUEST_HEADER + "\n".join(f"R-1;{i};A;Датчик;1;шт" for i in range(1, 202))
    with pytest.raises(ImportErrorInfo, match="200"):
        parse_upload("request", text.encode(), "request.csv", "text/csv")


def test_buyer_valid_requisites_and_partial_draft() -> None:
    """Принять контрольные учебные реквизиты и отдельно пустой черновик."""
    buyer = Buyer(
        company_name="ООО Покупатель Демо",
        inn="9901234561",
        kpp="990101001",
        ogrn="1269900000017",
        address="Учебный адрес",
        email="demo@example.test",
        phone="+7 (812) 555-12-34",
        bik="049999999",
        account="40702810600000000001",
        correspondent_account="30101810900000000001",
    )
    assert buyer.inn == "9901234561"
    assert Buyer().inn == ""
    assert Buyer(inn="990123456772", ogrn="326990000000010").kpp == ""


@pytest.mark.parametrize(
    "values",
    [
        {"inn": "9901234560"},
        {"inn": "0000000000"},
        {"inn": "123"},
        {"inn": "990123456770"},
        {"inn": "990123456772", "kpp": "990101001"},
        {"ogrn": "1269900000018"},
        {"inn": "9901234561", "ogrn": "326990000000010"},
        {"email": "name@"},
        {"phone": "не телефон"},
        {"address": "line\nline"},
        {"company_name": "К\u202eомпания"},
        {"bank_name": "x" * 201},
        {"bik": "04403065"},
        {"account": "40702810600000000001"},
        {"bik": "049999999", "account": "40702810600000000002"},
        {"bik": "049999999", "correspondent_account": "30101810900000000002"},
    ],
)
def test_bad_buyer_values_rejected(values: dict[str, str]) -> None:
    """Проверить контрольные цифры, согласованность и безопасный текст."""
    with pytest.raises(ValidationError):
        Buyer.model_validate(values)


def test_bool_is_not_quantity() -> None:
    """Программный вызов не должен превращать true в одну штуку."""
    with pytest.raises(ValidationError):
        RequestRow.model_validate(
            {
                "request_id": "R-1",
                "line": 1,
                "sku": "A",
                "name": "Датчик",
                "quantity": True,
                "unit": "шт",
            }
        )
