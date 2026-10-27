"""Входные строки, товары и проверяемый результат расчёта."""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ._schema import OptionalMoney, PositiveInteger, Schema


class RequestRow(Schema):
    """Исходная строка заявки: количество всегда в штуках."""

    request_id: Annotated[
        str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    ]
    line: PositiveInteger
    sku: Annotated[
        str,
        Field(
            max_length=80, pattern=r"^(?:[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_.-]*)?$"
        ),
    ]
    name: Annotated[str, Field(min_length=1, max_length=300)]
    quantity: PositiveInteger
    unit: Literal["шт"]


class PriceRow(Schema):
    """Строка прайса с ценой за указанную единицу продажи."""

    sku: Annotated[
        str,
        Field(
            min_length=1,
            max_length=80,
            pattern=r"^[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_.-]*$",
        ),
    ]
    name: Annotated[str, Field(min_length=1, max_length=300)]
    unit: Literal["шт", "упак"]
    pack_size: PositiveInteger
    price: OptionalMoney
    price_basis: Literal["net", "gross"]
    vat_rate: Annotated[Decimal, Field(ge=20, le=20, allow_inf_nan=False)]
    source: Annotated[str, Field(min_length=1, max_length=500)]

    @field_validator("vat_rate", mode="before")
    @classmethod
    def check_vat(cls, value: object) -> object:
        """Не допускать bool или произвольную ставку вместо учебных 20%."""
        if isinstance(value, bool):
            raise ValueError("В учебном примере укажите НДС 20.")
        return value

    @model_validator(mode="after")
    def check_package(self) -> Self:
        """Штука содержит одну штуку, упаковка — положительное количество."""
        if self.unit == "шт" and self.pack_size != 1:
            raise ValueError("Для единицы «шт» укажите pack_size 1.")
        return self


class Product(PriceRow):
    """Текущая сущность товара из последнего загруженного прайса."""

    id: str
    updated_at: str


class Status(StrEnum):
    """Рассчитанная строка или конкретное препятствие расчёту."""

    CONFIRMED = "confirmed"
    NEEDS_CLARIFICATION = "needs_clarification"
    MISSING_PRICE = "missing_price"
    NOT_FOUND = "not_found"
    QUANTITY_MISMATCH = "quantity_mismatch"


class QuoteLine(Schema):
    """Расчёт строки с исходным запросом и подтверждённым товаром."""

    request: RequestRow
    status: Status
    selected: Product | None = None
    sale_quantity: int | None = None
    discounted_price: Decimal | None = None
    unit_price_with_vat: Decimal | None = None
    total_with_vat: Decimal | None = None
    vat_amount: Decimal | None = None
    candidates: tuple[Product, ...] = ()
    note: str
    manually_selected: bool = False


class SourceFile(Schema):
    """Имя и отпечаток файла, из которого получены строки."""

    name: str
    sha256: str


class Quote(Schema):
    """Проверяемый результат расчёта выбранных строк."""

    request_id: str
    lines: tuple[QuoteLine, ...]
    discount_percent: Decimal
    vat_rate: Decimal = Decimal("20")
    currency: Literal["RUB"] = "RUB"
    confirmed_count: int
    unresolved_count: int
    is_complete: bool
    subtotal_with_vat: Decimal
    vat_amount: Decimal
    request_source: SourceFile | None = None
    price_source: SourceFile | None = None
