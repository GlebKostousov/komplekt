"""Поля, которые нельзя писать в журнал как есть."""

FORBIDDEN_LOG_FIELDS = frozenset(
    {
        "address",
        "addresses",
        "account",
        "api_key",
        "apikey",
        "authorization",
        "bik",
        "cookie",
        "correspondent_account",
        "hash",
        "inn",
        "kpp",
        "lat",
        "latitude",
        "lng",
        "lon",
        "longitude",
        "ogrn",
        "password",
        "passwd",
        "phone",
        "private_key",
        "pwd",
        "secret",
        "token",
    }
)
EMAIL_LOG_FIELDS = frozenset({"email"})
