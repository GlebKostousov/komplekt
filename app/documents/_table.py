"""Показать состав поставки и проверяемые суммы на странице A4."""

from reportlab.lib import colors
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.domain import Draft, QuoteLine, Status

from ._format import amount, percent
from ._style import AMBER, BOLD, FONT, INK, LINE, PAPER, style, text

STATUS_LABELS = {
    Status.NEEDS_CLARIFICATION: "Нужно уточнить товар",
    Status.MISSING_PRICE: "Цена не указана",
    Status.NOT_FOUND: "Товара нет в прайсе",
    Status.QUANTITY_MISMATCH: "Нужно согласовать количество упаковок",
}


def _item_details(line: QuoteLine) -> list[Flowable]:
    """Сохранить исходную позицию рядом с конкретным выбранным товаром."""
    product = line.selected
    name = product.name if product else line.request.name
    sku = product.sku if product else line.request.sku
    result: list[Flowable] = [text(name, style(size=8.5, leading=12, bold=True))]
    if sku:
        result.append(text(sku, style(size=7.3, leading=10, muted=True)))
    result.extend(_price_details(line))
    result.extend(_status_details(line))
    return result


def _price_details(line: QuoteLine) -> list[Flowable]:
    """Показать цену прайса и исходное название при ручном подборе."""
    product = line.selected
    if product is None:
        return []
    result: list[Flowable] = []
    if product.price is not None:
        basis = "без НДС" if product.price_basis == "net" else "с НДС"
        result.append(
            text(
                f"До скидки: {amount(product.price)} ₽ {basis}",
                style(size=7.2, leading=10, muted=True),
            )
        )
    result.extend(_selection_note(line))
    return result


def _selection_note(line: QuoteLine) -> list[Flowable]:
    """Не скрывать, когда поставщик предложил другой артикул."""
    if not line.manually_selected:
        return []
    source = f"В заявке: {line.request.name}"
    if line.request.sku:
        source += f" ({line.request.sku})"
    return [text(source, style(size=7.2, leading=10, muted=True))]


def _status_details(line: QuoteLine) -> list[Flowable]:
    """Сделать причину пустой суммы заметной непосредственно в строке."""
    if line.status == Status.CONFIRMED:
        return []
    warning_style = style(size=7.5, leading=10)
    warning_style.textColor = AMBER
    message = STATUS_LABELS[line.status]
    if line.status == Status.QUANTITY_MISMATCH:
        message = line.note
    return [text(message, warning_style)]


def _quantity(line: QuoteLine) -> Paragraph:
    """Отличить запрошенные штуки от упаковок, по которым считается цена."""
    product = line.selected
    if product is None or line.sale_quantity is None:
        return text(f"{line.request.quantity} шт.", style(size=8, leading=11))
    quantity = f"{line.sale_quantity} {product.unit}."
    if product.unit == "упак":
        quantity += f"\n{line.request.quantity} шт."
    return text(quantity, style(size=8, leading=11))


def _money_cell(value: str, *, bold: bool = False) -> Paragraph:
    """Выравнять денежное значение по правой стороне столбца."""
    return text(value, style(size=8, leading=11, right=True, bold=bold))


def items_table(quote: Draft, width: float) -> list[Flowable]:
    """Собрать таблицу с повторяющейся шапкой на следующих страницах."""
    headings = (
        "№",
        "Наименование / артикул",
        "Кол-во",
        "Цена\nс НДС, ₽",
        "Сумма\nс НДС, ₽",
        "В т. ч.\nНДС, ₽",
    )
    header_style = style(size=7.5, leading=10, bold=True)
    header_style.textColor = colors.white
    rows: list[list[object]] = [[text(value, header_style) for value in headings]]
    rows.extend(_item_row(line) for line in quote.lines)
    table = Table(
        rows,
        colWidths=[width * ratio for ratio in (0.045, 0.315, 0.11, 0.17, 0.19, 0.17)],
        repeatRows=1,
        splitByRow=1,
        splitInRow=1,
        hAlign="LEFT",
    )
    table.setStyle(_table_style())
    caption = text(
        "Цена за единицу продажи включает НДС и скидку "
        f"{percent(quote.discount_percent)}%.",
        style(size=8, leading=12, muted=True),
    )
    caption.style.keepWithNext = True
    return [caption, Spacer(1, 6), table]


def _item_row(line: QuoteLine) -> list[object]:
    """Оставить суммы нерешённой позиции пустыми, а явный ноль показать."""
    return [
        text(str(line.request.line), style(size=8, leading=11, muted=True)),
        _item_details(line),
        _quantity(line),
        _money_cell(amount(line.unit_price_with_vat)),
        _money_cell(amount(line.total_with_vat), bold=True),
        _money_cell(amount(line.vat_amount)),
    ]


def _table_style() -> TableStyle:
    """Оформить печатную таблицу без лишней вертикальной сетки."""
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
            ("FONTNAME", (0, 0), (-1, 0), BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT),
        ]
    )


def totals(quote: Draft, width: float) -> KeepTogether:
    """Назвать частичную сумму подытогом, а пустой расчёт не выдавать за ноль."""
    title = _total_title(quote)
    total_value = "Не рассчитан"
    vat_value = ""
    if quote.confirmed_count:
        total_value = f"{amount(quote.subtotal_with_vat)} ₽"
        vat_value = f"{amount(quote.vat_amount)} ₽"
    table = Table(
        [
            [
                text(title, style(size=10, leading=14, bold=True)),
                _money_cell(total_value, bold=True),
            ],
            [
                text("В том числе НДС 20%", style(size=8, leading=12, muted=True)),
                _money_cell(vat_value),
            ],
        ],
        colWidths=[width * 0.69, width * 0.31],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PAPER),
                ("LINEABOVE", (0, 0), (-1, 0), 0.7, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return KeepTogether([Spacer(1, 12), table])


def _total_title(quote: Draft) -> str:
    """Указать границы суммы в самом заголовке."""
    if not quote.calculation_complete:
        return "Подытог рассчитанных позиций"
    if quote.excluded_count:
        return "Итого по выбранным позициям"
    return "Итого с НДС"
