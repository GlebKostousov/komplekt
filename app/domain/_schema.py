"""Общие правила для проверенных данных приложения."""

import re
import unicodedata
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator


def clean_text(value: object) -> object:
    """Отклонить невидимые управляющие символы и убрать внешние пробелы."""
    if not isinstance(value, str):
        return value
    forbidden = any(
        ord(char) < 32 or unicodedata.category(char) in {"Cc", "Cf", "Cs"}
        for char in value
    )
    if forbidden:
        raise ValueError("Уберите переносы строк и невидимые управляющие символы.")
    return value.strip()


def parse_money(value: object) -> Decimal | None:
    """Прочитать цену без потери точности; пустую цену оставить пустой."""
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return _decimal_value(value)


def _decimal_value(value: object) -> Decimal | None:
    """Принять десятичную запись без экспоненты, валюты и bool."""
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise ValueError("Укажите цену числом, например 1250,50, без знака ₽.")
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    return _decimal_text(text)


def _decimal_text(text: str) -> Decimal:
    """Ограничить денежную запись двумя десятичными знаками."""
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", text):
        raise ValueError(
            "Укажите цену от 0, не больше двух знаков после запятой: 1250,50."
        )
    return Decimal(text)


def parse_discount(value: object) -> Decimal:
    """Прочитать обязательный процент с двумя знаками после запятой."""
    result = parse_money(value)
    if result is None or not result.is_finite() or not 0 <= result <= 100:
        raise ValueError("Укажите скидку от 0 до 100 процентов, например 10.")
    return result


def positive_integer(value: object) -> object:
    """Принять только целое положительное количество, не дробь или bool."""
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("Укажите целое число от 1 до 1000000, например 2.")
    if isinstance(value, str) and not re.fullmatch(r"[0-9]+", value.strip()):
        raise ValueError("Укажите целое число от 1 до 1000000, например 2.")
    return value


MoneyValue = Annotated[
    Decimal,
    Field(ge=0, le=Decimal("999999999999.99"), max_digits=14, decimal_places=2),
]
Money = Annotated[MoneyValue, BeforeValidator(parse_money)]
OptionalMoney = Annotated[MoneyValue | None, BeforeValidator(parse_money)]
Discount = Annotated[
    Decimal,
    BeforeValidator(parse_discount),
    Field(ge=0, le=100, decimal_places=2),
]
PositiveInteger = Annotated[
    int, BeforeValidator(positive_integer), Field(gt=0, le=1_000_000)
]


class Schema(BaseModel):
    """Запретить лишние поля и изменение проверенных данных."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @field_validator("*", mode="before")
    @classmethod
    def validate_text(cls, value: object) -> object:
        """Проверить текст на границе, сохраняя видимые символы буквально."""
        return clean_text(value)


class Issue(BaseModel):
    """Сообщить строку, столбец и понятный способ исправления."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    row: int | None = None
    field: str | None = None
    value: str | None = None
    message: str
