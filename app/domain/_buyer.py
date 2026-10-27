"""Проверка реквизитов покупателя без обращения к внешним реестрам."""

import re
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from ._schema import Schema

SHORT = Annotated[str, Field(max_length=200)]


def _digit_sum(value: str, weights: tuple[int, ...]) -> int:
    """Вычислить контрольную цифру ИНН по весам разрядов."""
    return (
        sum(int(char) * weight for char, weight in zip(value, weights, strict=True))
        % 11
        % 10
    )


def _inn_valid(value: str) -> bool:
    """Проверить 10- или 12-значный ИНН по контрольным цифрам."""
    if len(value) == 10:
        return _digit_sum(value[:9], (2, 4, 10, 3, 5, 9, 4, 6, 8)) == int(value[-1])
    first = _digit_sum(value[:10], (7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
    second = _digit_sum(value[:11], (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8))
    return first == int(value[10]) and second == int(value[11])


def _account_valid(value: str, prefix: str) -> bool:
    """Проверить контрольную сумму счёта с БИК банка."""
    digits = prefix + value
    return (
        sum(int(char) * (7, 1, 3)[index % 3] for index, char in enumerate(digits)) % 10
        == 0
    )


def _optional_digits(value: str, lengths: tuple[int, ...], message: str) -> str:
    """Проверить длину и цифры непустого реквизита."""
    if value and (len(value) not in lengths or not re.fullmatch(r"[0-9]+", value)):
        raise ValueError(message)
    return value


class Buyer(Schema):
    """Покупатель; незаполненные поля сохраняются в черновике пустыми."""

    company_name: Annotated[str, Field(max_length=200)] = ""
    inn: Annotated[str, Field(max_length=12)] = ""
    kpp: Annotated[str, Field(max_length=9)] = ""
    ogrn: Annotated[str, Field(max_length=15)] = ""
    address: Annotated[str, Field(max_length=350)] = ""
    contact_name: SHORT = ""
    email: Annotated[str, Field(max_length=254)] = ""
    phone: Annotated[str, Field(max_length=40)] = ""
    bank_name: SHORT = ""
    bik: Annotated[str, Field(max_length=9)] = ""
    account: Annotated[str, Field(max_length=20)] = ""
    correspondent_account: Annotated[str, Field(max_length=20)] = ""

    @field_validator("inn")
    @classmethod
    def validate_inn(cls, value: str) -> str:
        """Проверить число цифр и контрольную сумму ИНН."""
        _optional_digits(
            value,
            (10, 12),
            "В ИНН организации 10 цифр, в ИНН ИП — 12. Уберите пробелы и другие знаки.",
        )
        if value and (not _inn_valid(value) or len(set(value)) == 1):
            raise ValueError(
                "Проверьте ИНН: контрольные цифры не сходятся. "
                "Перепишите номер из реквизитов покупателя."
            )
        return value

    @field_validator("kpp")
    @classmethod
    def validate_kpp(cls, value: str) -> str:
        """Проверить девятизначный КПП."""
        return _optional_digits(
            value, (9,), "В КПП должно быть 9 цифр. Для ИП оставьте поле пустым."
        )

    @field_validator("ogrn")
    @classmethod
    def validate_ogrn(cls, value: str) -> str:
        """Проверить ОГРН или ОГРНИП и его контрольную цифру."""
        _optional_digits(value, (13, 15), "В ОГРН должно быть 13 цифр, в ОГРНИП — 15.")
        if not value:
            return value
        modulus = 11 if len(value) == 13 else 13
        if int(value[:-1]) % modulus % 10 != int(value[-1]) or len(set(value)) == 1:
            raise ValueError("Проверьте ОГРН: контрольная цифра не сходится.")
        return value

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Проверить один почтовый адрес без отображаемого имени."""
        if value and not re.fullmatch(r"[^\s@<>]+@[^\s@<>.]+(?:\.[^\s@<>.]+)+", value):
            raise ValueError("Укажите почту в виде name@example.ru, без пробелов.")
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        """Принять обычную запись телефона с 7–15 цифрами."""
        digits = re.sub(r"\D", "", value)
        if value and (
            not re.fullmatch(r"\+?[0-9 ()-]+", value) or not 7 <= len(digits) <= 15
        ):
            raise ValueError(
                "Укажите телефон с 7–15 цифрами, например +7 (812) 555-12-34."
            )
        return value

    @field_validator("bik")
    @classmethod
    def validate_bik(cls, value: str) -> str:
        """Проверить девять цифр БИК без подтверждения существования банка."""
        return _optional_digits(value, (9,), "В БИК должно быть 9 цифр без пробелов.")

    @field_validator("account", "correspondent_account")
    @classmethod
    def validate_account(cls, value: str) -> str:
        """Проверить двадцать цифр банковского счёта."""
        return _optional_digits(
            value, (20,), "В номере счёта должно быть 20 цифр без пробелов."
        )

    @model_validator(mode="after")
    def check_entity(self) -> Self:
        """Не смешивать реквизиты организации и ИП."""
        if len(self.inn) == 12 and self.kpp:
            raise ValueError("У ИП нет КПП. Оставьте поле «КПП» пустым.")
        wrong_ogrn = self.ogrn and self.inn and len(self.ogrn) - len(self.inn) != 3
        if wrong_ogrn:
            raise ValueError(
                "ИНН и ОГРН относятся к разным типам покупателя. "
                "Организация: 10 и 13 цифр; ИП: 12 и 15."
            )
        return self

    @model_validator(mode="after")
    def check_bank(self) -> Self:
        """Проверить связь банковских счетов с введённым БИК."""
        if (self.account or self.correspondent_account) and not self.bik:
            raise ValueError("Добавьте БИК банка, чтобы проверить номер счёта.")
        if self.account and not _account_valid(self.account, self.bik[-3:]):
            raise ValueError(
                "Расчётный счёт не соответствует БИК. Проверьте оба номера."
            )
        return self

    @model_validator(mode="after")
    def check_correspondent_account(self) -> Self:
        """Проверить корреспондентский счёт с префиксом из БИК."""
        if self.correspondent_account and not _account_valid(
            self.correspondent_account, "0" + self.bik[4:6]
        ):
            raise ValueError(
                "Корреспондентский счёт не соответствует БИК. Проверьте оба номера."
            )
        return self


class BuyerDraft(Schema):
    """Черновик реквизитов: длина ограничена, контрольные цифры ещё не проверяются."""

    company_name: Annotated[str, Field(max_length=200)] = ""
    inn: Annotated[str, Field(max_length=12)] = ""
    kpp: Annotated[str, Field(max_length=9)] = ""
    ogrn: Annotated[str, Field(max_length=15)] = ""
    address: Annotated[str, Field(max_length=350)] = ""
    contact_name: SHORT = ""
    email: Annotated[str, Field(max_length=254)] = ""
    phone: Annotated[str, Field(max_length=40)] = ""
    bank_name: SHORT = ""
    bik: Annotated[str, Field(max_length=9)] = ""
    account: Annotated[str, Field(max_length=20)] = ""
    correspondent_account: Annotated[str, Field(max_length=20)] = ""


class Seller(Schema):
    """Фиксированные реквизиты вымышленного учебного продавца."""

    company_name: str
    inn: str
    kpp: str
    ogrn: str
    address: str
    phone: str
    email: str
    website: str
    bank_name: str
    bik: str
    account: str
    correspondent_account: str
    manager: str
    manager_title: str
