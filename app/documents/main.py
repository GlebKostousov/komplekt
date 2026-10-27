"""Сформировать самостоятельный PDF из сохранённого снимка КП."""

from functools import partial
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, SimpleDocTemplate, Spacer

from app.domain import SavedQuote

from ._company import default_seller
from ._parts import (
    buyer_section,
    draft_warning,
    header,
    seller_section,
    source_note,
    subject_section,
    terms_section,
)
from ._style import FONT, LINE, MUTED, register_fonts
from ._table import items_table, totals

__all__ = ["default_seller", "render_pdf"]


def _footer(canvas: Canvas, document: SimpleDocTemplate) -> None:
    """Повторить отметку об учебных реквизитах и номер каждой страницы."""
    canvas.saveState()
    width, _height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(document.leftMargin, 17 * mm, width - document.rightMargin, 17 * mm)
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(
        document.leftMargin,
        12.5 * mm,
        "Учебный образец. Компания и реквизиты вымышлены.",
    )
    canvas.drawRightString(
        width - document.rightMargin, 12.5 * mm, f"Стр. {document.page}"
    )
    canvas.restoreState()


def _story(saved: SavedQuote, width: float) -> list[Flowable]:
    """Собрать разделы в порядке чтения обычного коммерческого предложения."""
    quote = saved.quote
    result: list[Flowable] = []
    result.extend(header(saved, width))
    result.extend(draft_warning(quote, width))
    result.extend(buyer_section(quote.buyer))
    result.extend(subject_section(quote))
    result.extend(items_table(quote, width))
    result.append(totals(quote, width))
    result.append(Spacer(1, 5))
    result.append(source_note(quote))
    result.extend(terms_section(saved.seller))
    result.extend(seller_section(saved.seller))
    return result


def _later_page(number: str, canvas: Canvas, document: SimpleDocTemplate) -> None:
    """Связать продолжение таблицы или условий с номером предложения."""
    _footer(canvas, document)
    canvas.saveState()
    width, height = A4
    canvas.setFont(FONT, 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(document.leftMargin, height - 10 * mm, "ЛАДОГА КОМПЛЕКТ")
    canvas.drawRightString(
        width - document.rightMargin, height - 10 * mm, f"КП № {number} · Продолжение"
    )
    canvas.restoreState()


def render_pdf(saved: SavedQuote) -> bytes:
    """Создать PDF без повторного чтения прайса или изменения сохранённых данных.

    Args:
        saved: Неизменяемый снимок покупателя, продавца, строк и расчёта.

    Returns:
        Готовый PDF с встроенным кириллическим шрифтом.
    """
    register_fonts()
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=15 * mm,
        bottomMargin=23 * mm,
        title=f"Коммерческое предложение {saved.number}",
        author=saved.seller.company_name,
        subject="Поставка комплектующих по заявке покупателя",
        creator="Комплект - учебное приложение для подготовки КП",
        pageCompression=1,
        allowSplitting=1,
    )
    document.build(
        _story(saved, document.width),
        onFirstPage=_footer,
        onLaterPages=partial(_later_page, saved.number),
    )
    return output.getvalue()
