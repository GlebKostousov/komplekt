"""Форматировать деньги и даты без зависимости от локали компьютера."""

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal


def amount(value: Decimal | None) -> str:
    """Показать копейки, сохранив отличие пустой цены от нуля."""
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ").replace(".", ",")


def percent(value: Decimal) -> str:
    """Убрать лишние нули в проценте скидки."""
    return format(value.normalize(), "f").replace(".", ",")


def local_date(value: str) -> str:
    """Показать дату выпуска по московскому времени."""
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y")
