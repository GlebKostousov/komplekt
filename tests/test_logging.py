"""Журнал не пишет секреты и маскирует почту."""

import logging

from app.logging import drop_forbidden_fields, mask_email

_LOGGER = logging.getLogger("komplekt.test.logging")


def test_email_mask_hides_the_address() -> None:
    """Маска оставляет два знака имени и один знак домена."""
    assert mask_email("ivan@example.test") == "iv***@e***"
    assert mask_email("a@example.test") == "a***@e***"
    assert mask_email("не адрес") == "***"


def test_secrets_are_removed_but_error_code_stays() -> None:
    """Вложенные секреты вырезаются, код ошибки остаётся."""
    cleaned = drop_forbidden_fields(
        _LOGGER,
        "warning",
        {
            "event": "app.domain_error",
            "code": "CONFLICT",
            "Password": "secret",
            "email": "ivan@example.test",
            "buyer": {
                "INN": "9900000000",
                "email": "anna@example.test",
                "company_name": "Демо",
            },
            "rows": [{"phone": "+7000", "sku": "A-1"}, "plain"],
            "tags": ("ok", {"token": "abc"}),
        },
    )
    assert cleaned["code"] == "CONFLICT"
    assert "Password" not in cleaned
    assert cleaned["email"] == "iv***@e***"
    buyer = cleaned["buyer"]
    assert isinstance(buyer, dict)
    assert "INN" not in buyer
    assert buyer["email"] == "an***@e***"
    assert buyer["company_name"] == "Демо"
    rows = cleaned["rows"]
    assert isinstance(rows, list)
    assert rows[0] == {"sku": "A-1"}
    assert rows[1] == "plain"
    assert cleaned["tags"] == ["ok", {}]
