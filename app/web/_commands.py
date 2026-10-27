"""Проверять команды браузера до изменения сохранённых данных."""

from typing import Annotated, Literal

from pydantic import Field

from app.domain import (
    Buyer,
    BuyerDraft,
    Discount,
    Issue,
    OptionalMoney,
    PriceRow,
    RequestRow,
    Schema,
)

Identifier = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
RequestId = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")]


class Command(Schema):
    """Требовать номер состояния, на котором основана правка."""

    revision: Annotated[int, Field(strict=True, ge=0)]


class CommitImport(Command):
    """Применить ранее проверенную загрузку."""

    token: Identifier


class EditPrice(Command):
    """Изменить общую цену товара, сохранив отсутствие цены как None."""

    price: OptionalMoney
    source: Annotated[str, Field(min_length=1, max_length=500)]


class EditBuyer(Command):
    """Сохранить проверенные реквизиты покупателя."""

    buyer: Buyer


class SaveDraft(Command):
    """Сохранить незаконченные реквизиты и текст скидки."""

    buyer_draft: BuyerDraft
    discount_draft: Annotated[str, Field(max_length=16)]


class SelectLines(Command):
    """Выбрать существующие строки одной заявки для включения в КП."""

    lines: Annotated[
        tuple[Annotated[int, Field(strict=True, gt=0, le=1_000_000)], ...],
        Field(max_length=200),
    ]


class ChooseProduct(Command):
    """Явно выбрать товар текущего прайса или сбросить выбор."""

    product_id: Identifier | None


class EditDiscount(Command):
    """Изменить скидку без вычислений с плавающей точкой."""

    discount_percent: Discount


class CreateQuote(Command):
    """Выпустить PDF после подтверждения неполных данных."""

    request_id: RequestId
    allow_incomplete: Annotated[bool, Field(strict=True)] = False


class Changes(Schema):
    """Объяснить последствия применения файла."""

    added: int
    changed: int
    removed: int
    replaces_request: bool = False


class ImportPreview(Schema):
    """Показать проверенную загрузку, не меняя рабочие записи."""

    token: str
    revision: int
    kind: Literal["price", "request"]
    filename: str
    row_count: int
    request_id: str | None
    rows: tuple[PriceRow | RequestRow, ...]
    warnings: tuple[Issue, ...]
    changes: Changes
    expires_at: str
