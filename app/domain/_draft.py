"""Подготовить КП из выбранных строк без ввода-вывода."""

from decimal import Decimal

from ._calculate import _calculate_line, _from_name, _from_sku
from ._errors import InputError
from ._models import Product, QuoteLine, RequestRow, SourceFile, Status
from ._state import Catalog, Draft, RequestRecord


def _selected_rows(request: RequestRecord) -> tuple[RequestRow, ...]:
    """Оставить только явно выбранные строки текущей заявки."""
    selected = set(request.selected_lines)
    available = {row.line for row in request.rows}
    if len(selected) != len(request.selected_lines) or not selected <= available:
        raise InputError("Выберите строки из этой заявки, без повторений.")
    return tuple(row for row in request.rows if row.line in selected)


def _line(
    row: RequestRow, products: tuple[Product, ...], request: RequestRecord
) -> QuoteLine:
    """Применить явный выбор, иначе использовать строгий подбор."""
    choice = request.choices.get(str(row.line))
    if choice:
        return _chosen_line(row, products, request, choice)
    index = {product.sku: product for product in products}
    if row.sku:
        return _from_sku(row, index, request.discount_percent)
    return _from_name(row, products, request.discount_percent)


def _chosen_line(
    row: RequestRow,
    products: tuple[Product, ...],
    request: RequestRecord,
    choice: str,
) -> QuoteLine:
    """Проверить принадлежность ручного выбора текущему прайсу."""
    product = next((item for item in products if item.id == choice), None)
    if product is None:
        raise InputError(
            "Выбранного товара больше нет в текущем прайсе. Выберите товар заново."
        )
    line = _calculate_line(row, product, request.discount_percent)
    return line.model_copy(update={"manually_selected": True})


def _sum(lines: tuple[QuoteLine, ...], field: str) -> Decimal:
    """Сложить рассчитанные значения, оставляя пропуски за пределами суммы."""
    return sum(
        (getattr(line, field) or Decimal("0.00") for line in lines),
        Decimal("0.00"),
    )


def build_draft(request: RequestRecord, catalog: Catalog | None) -> Draft:
    """Посчитать выбранные строки и отдельно проверить заполнение покупателя."""
    products = catalog.products if catalog else ()
    rows = _selected_rows(request)
    lines = tuple(_line(row, products, request) for row in rows)
    confirmed = tuple(line for line in lines if line.status == Status.CONFIRMED)
    missing = tuple(
        key
        for key in ("company_name", "inn", "address")
        if not getattr(request.buyer, key)
    )
    calculated = bool(lines) and len(confirmed) == len(lines)
    return Draft(
        request_id=request.request_id,
        lines=lines,
        discount_percent=request.discount_percent,
        confirmed_count=len(confirmed),
        unresolved_count=len(lines) - len(confirmed),
        selected_count=len(lines),
        excluded_count=len(request.rows) - len(lines),
        calculation_complete=calculated,
        is_complete=calculated and not missing,
        missing_buyer_fields=missing,
        subtotal_with_vat=_sum(confirmed, "total_with_vat"),
        vat_amount=_sum(confirmed, "vat_amount"),
        buyer=request.buyer,
        request_source=SourceFile(name=request.filename, sha256=request.sha256),
        price_source=SourceFile(name=catalog.filename, sha256=catalog.sha256)
        if catalog
        else None,
    )
