"""Целые копейки и базисные пункты процента в столбцах SQLite."""

from decimal import ROUND_HALF_UP, Decimal


def kopecks(value: Decimal | None) -> int | None:
    """Перевести сумму в копейки.

    Args:
        value: Сумма с двумя знаками либо пустая цена.

    Returns:
        Целое число копеек или ``None``.
    """
    if value is None:
        return None
    cents = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(cents * 100)


def money_required(value: int) -> Decimal:
    """Вернуть обязательную сумму из копеек.

    Args:
        value: Копейки, столбец не бывает пустым.

    Returns:
        Сумма.

    Raises:
        RuntimeError: В столбце оказалось пустое значение.
    """
    result = from_kopecks(value)
    if result is None:
        message = "Пустая сумма в обязательном столбце."
        raise RuntimeError(message)
    return result


def from_kopecks(value: int | None) -> Decimal | None:
    """Вернуть сумму из копеек.

    Args:
        value: Копейки либо пустая цена.

    Returns:
        Точная десятичная сумма или ``None``.
    """
    if value is None:
        return None
    return Decimal(value) / Decimal(100)


def basis_points(value: Decimal) -> int:
    """Перевести процент в сотые доли процента.

    Args:
        value: Процент или ставка.

    Returns:
        Целое: 10% становится 1000.
    """
    return int(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * 100)


def from_basis_points(value: int) -> Decimal:
    """Вернуть процент из сотых долей.

    Args:
        value: Целое в сотых долях процента.

    Returns:
        Процент.
    """
    return Decimal(value) / Decimal(100)
