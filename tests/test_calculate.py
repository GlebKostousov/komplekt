"""Проверить расчёт по независимым примерам и исходному заданию."""

from decimal import Decimal
from pathlib import Path

import pytest

from app.domain import (
    Buyer,
    Catalog,
    InputError,
    PriceRow,
    Product,
    RequestRecord,
    RequestRow,
    Status,
    build_draft,
    build_quote,
)
from app.imports import parse_upload

DATA = Path(__file__).resolve().parents[1] / "data"
STAMP = "2026-10-27T12:00:00+03:00"


def loaded() -> tuple[RequestRecord, Catalog]:
    """Собрать сущности из неизменённых исходных CSV."""
    requests = parse_upload(
        "request", (DATA / "request.csv").read_bytes(), "request.csv", "text/csv"
    )
    prices = parse_upload(
        "price", (DATA / "price.csv").read_bytes(), "price.csv", "text/csv"
    )
    rows = tuple(row for row in requests.rows if isinstance(row, RequestRow))
    products = tuple(
        Product.model_validate(
            {**row.model_dump(), "id": f"item-{row.sku}", "updated_at": STAMP}
        )
        for row in prices.rows
    )
    request = RequestRecord(
        request_id="REQ-001",
        filename="request.csv",
        sha256=requests.sha256,
        uploaded_at=STAMP,
        rows=rows,
        selected_lines=(1, 2, 3, 4, 5),
    )
    catalog = Catalog(
        generation="one",
        filename="price.csv",
        sha256=prices.sha256,
        uploaded_at=STAMP,
        products=products,
    )
    return request, catalog


def request_row(quantity: int = 2, sku: str = "A-100") -> RequestRow:
    """Создать одну исходную позицию."""
    return RequestRow(
        request_id="REQ-001",
        line=1,
        sku=sku,
        name="Датчик A",
        quantity=quantity,
        unit="шт",
    )


def product(
    value: str | None = "1000", basis: str = "net", pack_size: int = 1
) -> Product:
    """Подготовить подтверждённый товар с заданной единицей продажи."""
    return Product.model_validate(
        {
            "id": "item-A-100",
            "updated_at": STAMP,
            "sku": "A-100",
            "name": "Датчик A",
            "price": value,
            "price_basis": basis,
            "vat_rate": "20",
            "source": "Учебный прайс",
            "unit": "упак" if pack_size > 1 else "шт",
            "pack_size": pack_size,
        }
    )


def test_baseline_with_original_inputs() -> None:
    """Из пяти строк подтвердить две: 3060 рублей, НДС 510."""
    request, catalog = loaded()
    draft = build_draft(request, catalog)
    assert draft.subtotal_with_vat == Decimal("3060.00")
    assert draft.vat_amount == Decimal("510.00")
    assert draft.confirmed_count == 2
    assert draft.unresolved_count == 3
    assert draft.selected_count == 5
    assert draft.missing_buyer_fields == ("company_name", "inn", "address")
    sensor, packs, ambiguous, no_price, absent = draft.lines
    assert sensor.unit_price_with_vat == Decimal("1080.00")
    assert sensor.total_with_vat == Decimal("2160.00")
    assert sensor.vat_amount == Decimal("360.00")
    assert packs.request.quantity == 20
    assert packs.sale_quantity == 2
    assert packs.total_with_vat == Decimal("900.00")
    assert packs.vat_amount == Decimal("150.00")
    assert ambiguous.status is Status.NEEDS_CLARIFICATION
    assert {row.sku for row in ambiguous.candidates} == {"M-10", "M-20"}
    assert no_price.status is Status.MISSING_PRICE
    assert absent.status is Status.NOT_FOUND
    assert all(row.total_with_vat is None for row in draft.lines[2:])


def test_changed_entity_price_affects_next_draft() -> None:
    """Изменение цены A-100 на 1100 даёт 3276 рублей и НДС 546."""
    request, catalog = loaded()
    updated = catalog.products[0].model_copy(update={"price": Decimal("1100")})
    changed = catalog.model_copy(update={"products": (updated, *catalog.products[1:])})
    draft = build_draft(request, changed)
    assert draft.subtotal_with_vat == Decimal("3276.00")
    assert draft.vat_amount == Decimal("546.00")


def test_explicit_choice_and_selection_preserve_original() -> None:
    """Выбор M-20 разрешает неоднозначность, исходное название не подменяется."""
    request, catalog = loaded()
    request = request.model_copy(
        update={
            "selected_lines": (1, 3),
            "choices": {"3": "item-M-20"},
            "buyer": Buyer(
                company_name="ООО Пример", inn="9901234561", address="Учебный адрес"
            ),
        }
    )
    draft = build_draft(request, catalog)
    assert draft.is_complete
    assert draft.selected_count == 2
    assert draft.excluded_count == 3
    assert draft.subtotal_with_vat == Decimal("2538.00")
    chosen = draft.lines[1]
    assert chosen.request.name == "Фильтр М"
    assert chosen.selected is not None and chosen.selected.sku == "M-20"
    assert chosen.manually_selected
    assert chosen.total_with_vat == Decimal("378.00")


def test_no_catalog_and_empty_selection_are_not_complete() -> None:
    """Отсутствующий прайс и снятые галочки не дают готовое пустое КП."""
    request, _ = loaded()
    no_catalog = build_draft(request, None)
    assert no_catalog.unresolved_count == 5
    assert not no_catalog.is_complete
    assert no_catalog.subtotal_with_vat == Decimal("0.00")
    empty = build_draft(request.model_copy(update={"selected_lines": ()}), None)
    assert empty.lines == ()
    assert not empty.calculation_complete
    assert not empty.is_complete


def test_obsolete_choice_is_rejected() -> None:
    """Не использовать товар из удалённого прайса."""
    request, catalog = loaded()
    request = request.model_copy(update={"choices": {"3": "deleted-product"}})
    with pytest.raises(InputError, match="больше нет"):
        build_draft(request, catalog)


@pytest.mark.parametrize("selected", [(99,), (1, 1)])
def test_selection_cannot_invent_lines(selected: tuple[int, ...]) -> None:
    """В расчёт входят только уникальные номера текущей заявки."""
    request, catalog = loaded()
    with pytest.raises(InputError, match="строки"):
        build_draft(request.model_copy(update={"selected_lines": selected}), catalog)


@pytest.mark.parametrize("sku", ["X-999", "a-100"])
def test_unknown_sku_does_not_fall_back_to_name(sku: str) -> None:
    """Не подменять отсутствующий артикул совпадающим названием."""
    quote = build_quote((request_row(sku=sku),), (product(),))
    assert quote.lines[0].status is Status.NOT_FOUND
    assert quote.lines[0].selected is None


@pytest.mark.parametrize(
    ("basis", "gross", "total", "vat"),
    [("net", "1.25", "3.75", "0.63"), ("gross", "1.04", "3.12", "0.52")],
)
def test_rounding_uses_visible_unit_price(
    basis: str, gross: str, total: str, vat: str
) -> None:
    """1,035 округляется вверх, сумма совпадает с видимой ценой на количество."""
    quote = build_quote((request_row(3),), (product("1.15", basis),))
    line = quote.lines[0]
    assert line.discounted_price == Decimal("1.04")
    assert line.unit_price_with_vat == Decimal(gross)
    assert line.total_with_vat == Decimal(total)
    assert line.vat_amount == Decimal(vat)


def test_missing_price_and_explicit_zero_are_different() -> None:
    """Пустая цена не превращается в бесплатный товар."""
    zero = build_quote((request_row(),), (product("0"),))
    empty = build_quote((request_row(),), (product(None),))
    assert zero.lines[0].total_with_vat == Decimal("0.00")
    assert zero.lines[0].status is Status.CONFIRMED
    assert empty.lines[0].total_with_vat is None
    assert empty.lines[0].status is Status.MISSING_PRICE


def test_odd_pack_count_does_not_round_order_up() -> None:
    """21 штуку нельзя без согласования превратить в 3 упаковки по 10."""
    quote = build_quote((request_row(21),), (product("500", "gross", 10),))
    assert quote.lines[0].status is Status.QUANTITY_MISMATCH
    assert quote.lines[0].sale_quantity is None
    assert quote.lines[0].total_with_vat is None


def test_discount_fifteen_percent() -> None:
    """Изменение правила скидки даёт независимый контрольный результат."""
    request, catalog = loaded()
    result = build_draft(
        request.model_copy(update={"discount_percent": Decimal("15")}), catalog
    )
    assert result.subtotal_with_vat == Decimal("2890.00")
    assert result.vat_amount == Decimal("481.67")


def test_plain_price_row_remains_usable_by_pure_calculation() -> None:
    """Расчёт можно использовать отдельно от хранилища и сущностей."""
    row = PriceRow.model_validate(product().model_dump(exclude={"id", "updated_at"}))
    assert build_quote((request_row(),), (row,)).subtotal_with_vat == Decimal("2160.00")
