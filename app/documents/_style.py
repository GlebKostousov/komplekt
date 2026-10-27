"""Подготовить шрифты и типографику печатного документа."""

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph

INK = colors.HexColor("#18302F")
MUTED = colors.HexColor("#66726F")
LINE = colors.HexColor("#D9DFDB")
PAPER = colors.HexColor("#F2F5F1")
AMBER = colors.HexColor("#845112")
AMBER_PAPER = colors.HexColor("#FFF5DD")
FONT = "KomplektSans"
BOLD = "KomplektSans-Bold"


def register_fonts() -> None:
    """Встроить кириллицу из поставляемых вместе с приложением шрифтов."""
    font_dir = Path(__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont(FONT, str(font_dir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(font_dir / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=BOLD, italic=FONT)


def style(
    name: str = "Body",
    *,
    size: float = 9,
    leading: float = 13,
    bold: bool = False,
    muted: bool = False,
    right: bool = False,
) -> ParagraphStyle:
    """Создать независимый стиль абзаца с переносом длинных значений."""
    return ParagraphStyle(
        name,
        fontName=BOLD if bold else FONT,
        fontSize=size,
        leading=leading,
        textColor=MUTED if muted else INK,
        alignment=TA_RIGHT if right else TA_LEFT,
        splitLongWords=True,
        spaceAfter=0,
        allowWidows=0,
        allowOrphans=0,
    )


def text(value: str, paragraph_style: ParagraphStyle | None = None) -> Paragraph:
    """Вывести пользовательский текст буквально, не исполняя PDF-разметку."""
    safe = escape(value).replace("\n", "<br/>")
    return Paragraph(safe, paragraph_style or style())


def label(value: str) -> Paragraph:
    """Выделить заголовок следующего раздела."""
    result = style("Section", size=9, leading=12, bold=True)
    result.spaceBefore = 13
    result.spaceAfter = 6
    result.keepWithNext = True
    return text(value, result)
