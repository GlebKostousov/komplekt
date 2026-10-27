"""Собрать шапку, реквизиты и условия коммерческого предложения."""

from reportlab.lib import colors
from reportlab.platypus import Flowable, Paragraph, Spacer, Table, TableStyle

from app.domain import Buyer, Draft, SavedQuote, Seller

from ._company import SUBJECT, TERMS, VAT_NOTE
from ._format import local_date
from ._style import AMBER, AMBER_PAPER, LINE, label, style, text


def header(saved: SavedQuote, width: float) -> list[Flowable]:
    """Показать поставщика, номер, дату и предмет предложения."""
    brand = text("ЛАДОГА КОМПЛЕКТ", style(size=16, leading=20, bold=True))
    contact = text(
        f"{saved.seller.phone}\n{saved.seller.email}",
        style(size=8, leading=12, right=True),
    )
    table = Table([[brand, contact]], colWidths=[width * 0.51, width * 0.49])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                ("LINEBELOW", (0, 0), (-1, -1), 0.8, LINE),
            ]
        )
    )
    return [
        table,
        Spacer(1, 16),
        text("Коммерческое предложение", style(size=20, leading=25, bold=True)),
        Spacer(1, 5),
        text(
            f"№ {saved.number} от {local_date(saved.created_at)}  ·  "
            f"Заявка {saved.quote.request_id}",
            style(size=9, leading=13, muted=True),
        ),
        Spacer(1, 12),
    ]


def draft_warning(quote: Draft, width: float) -> list[Flowable]:
    """Пометить неполный расчёт и неполные реквизиты внутри самого PDF."""
    if quote.is_complete:
        return []
    warning_style = style(size=9, leading=13, bold=True)
    warning_style.textColor = AMBER
    lines = _warning_lines(quote)
    warning = Table(
        [[text("\n".join(lines), warning_style)]],
        colWidths=[width],
    )
    warning.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), AMBER_PAPER),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6D4AE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [warning, Spacer(1, 12)]


def _warning_lines(quote: Draft) -> list[str]:
    """Описать только те ограничения, которые есть в данном снимке."""
    result = []
    if not quote.calculation_complete:
        result.append("Черновик. Не все позиции рассчитаны.")
        result.append(
            f"В подытог включено {quote.confirmed_count} из "
            f"{quote.selected_count} позиций."
        )
    if quote.missing_buyer_fields:
        result.append("Черновик. Не заполнены обязательные реквизиты покупателя.")
    return result


def _joined_fields(values: tuple[tuple[str, str], ...]) -> str:
    """Соединить только заполненные реквизиты."""
    return "  ·  ".join(f"{name} {value}" for name, value in values if value)


def buyer_section(buyer: Buyer) -> list[Flowable]:
    """Вывести адресата и предоставленные покупателем реквизиты."""
    rows = [
        buyer.company_name or "Покупатель пока не указан",
        _joined_fields((("ИНН", buyer.inn), ("КПП", buyer.kpp))),
        _joined_fields((("ОГРН / ОГРНИП", buyer.ogrn),)),
        buyer.address,
        _joined_fields((("Контакт:", buyer.contact_name),)),
        _joined_fields((("Тел.:", buyer.phone), ("Email:", buyer.email))),
    ]
    result: list[Flowable] = [label("Покупатель")]
    result.extend(text(row, style(size=9, leading=13)) for row in rows if row)
    result.extend(_buyer_bank(buyer))
    return result


def _buyer_bank(buyer: Buyer) -> list[Flowable]:
    """Добавить банковские реквизиты, если они были предоставлены."""
    rows = [
        _joined_fields((("Банк:", buyer.bank_name), ("БИК", buyer.bik))),
        _joined_fields((("Р/с", buyer.account),)),
        _joined_fields((("К/с", buyer.correspondent_account),)),
    ]
    return [text(row, style(size=8, leading=12, muted=True)) for row in rows if row]


def subject_section(quote: Draft) -> list[Flowable]:
    """Использовать один фиксированный предмет предложения."""
    result: list[Flowable] = [label("Предмет предложения"), text(SUBJECT)]
    if quote.excluded_count:
        result.append(
            text(
                f"В предложение включено {quote.selected_count} из "
                f"{quote.selected_count + quote.excluded_count} строк заявки. "
                "Остальные позиции не входят в этот расчёт.",
                style(size=8, leading=12, muted=True),
            )
        )
    result.append(Spacer(1, 12))
    return result


def terms_section(seller: Seller) -> list[Flowable]:
    """Добавить стандартные условия и понятный следующий шаг."""
    result: list[Flowable] = [label("Условия предложения")]
    result.extend(text(f"{name}: {value}") for name, value in TERMS)
    result.append(text(VAT_NOTE, style(size=8, leading=12, muted=True)))
    result.extend(
        [
            Spacer(1, 9),
            text(
                "Пожалуйста, подтвердите состав заказа и реквизиты ответным "
                "письмом. После согласования подготовим счёт."
            ),
            Spacer(1, 8),
            text(seller.manager, style(bold=True)),
            text(seller.manager_title, style(size=8, leading=12, muted=True)),
            text(f"{seller.phone}  ·  {seller.email}", style(size=8, leading=12)),
        ]
    )
    return result


def seller_section(seller: Seller) -> list[Flowable]:
    """Указать все реквизиты вымышленного поставщика без изображения подписи."""
    rows = (
        seller.company_name,
        f"ИНН {seller.inn}  ·  КПП {seller.kpp}  ·  ОГРН {seller.ogrn}",
        seller.address,
        f"{seller.bank_name}  ·  БИК {seller.bik}",
        f"Р/с {seller.account}  ·  К/с {seller.correspondent_account}",
        f"Сайт: {seller.website}",
    )
    result: list[Flowable] = [label("Реквизиты поставщика")]
    result.extend(text(row, style(size=7.7, leading=11, muted=True)) for row in rows)
    return result


def source_note(quote: Draft) -> Paragraph:
    """Показать, из каких файлов получен сохранённый расчёт."""
    price = quote.price_source.name if quote.price_source else "не загружен"
    request = quote.request_source.name if quote.request_source else "не указан"
    return text(
        f"Загруженные файлы: заявка «{request}»; прайс «{price}».",
        style(size=7.5, leading=11, muted=True),
    )
