"""Снимки данных, используемые хранилищем, интерфейсом и PDF."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field

from ._buyer import Buyer, BuyerDraft, Seller
from ._models import Product, Quote, RequestRow
from ._schema import Discount, Schema


class Catalog(Schema):
    """Товары только текущего прайса и исходный файл."""

    generation: str
    filename: str
    uploaded_at: str
    sha256: str
    products: tuple[Product, ...]


class RequestRecord(Schema):
    """Одна сохранённая заявка с выбором строк и покупателем."""

    request_id: str
    filename: str
    sha256: str
    uploaded_at: str
    rows: tuple[RequestRow, ...]
    buyer: Buyer = Field(default_factory=Buyer)
    buyer_draft: BuyerDraft = Field(default_factory=BuyerDraft)
    selected_lines: tuple[int, ...]
    choices: dict[str, str] = Field(default_factory=dict)
    discount_percent: Discount = Decimal("10")
    discount_draft: Annotated[str, Field(max_length=16)] = "10"


class Draft(Quote):
    """Результат подготовки КП до выпуска файла."""

    selected_count: int
    excluded_count: int
    calculation_complete: bool
    missing_buyer_fields: tuple[str, ...]
    buyer: Buyer


class QuoteSummary(Schema):
    """Краткая строка в истории сохранённых КП."""

    id: str
    number: str
    created_at: str
    request_id: str
    buyer_name: str
    subtotal_with_vat: Decimal
    vat_amount: Decimal
    is_complete: bool
    selected_count: int
    unresolved_count: int
    filename: str


class SavedQuote(Schema):
    """Неизменяемый снимок данных выпущенного PDF."""

    id: str
    number: str
    created_at: str
    seller: Seller
    quote: Draft


class State(Schema):
    """Состояние локальной учебной рабочей области."""

    revision: int
    catalog: Catalog | None
    requests: tuple[RequestRecord, ...]
    quotes: tuple[QuoteSummary, ...]
    seller: Seller
    assumptions: tuple[str, ...]
