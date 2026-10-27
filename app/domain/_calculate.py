"""Подобрать товары и рассчитать черновик без файлов и побочных эффектов."""

import re
from decimal import ROUND_HALF_UP, Decimal

from ._errors import InputError
from ._models import PriceRow, Product, Quote, QuoteLine, RequestRow, Status


def money(value: Decimal) -> Decimal:
    """Округлить деньги до копеек по единому правилу.

    Args:
        value: Рассчитанная сумма.

    Returns:
        Сумма с двумя десятичными знаками.
    """
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _require_unique(values: tuple[str | int, ...], label: str) -> None:
    """Отвергнуть дубли ключей до создания индекса.

    Args:
        values: Ключи входных строк.
        label: Название ключа для сообщения.

    Raises:
        InputError: Найдены повторяющиеся ключи.
    """
    if len(values) != len(set(values)):
        message = f"Повторяется {label}. Уточните исходные данные."
        raise InputError(message)


def _validate_request(requests: tuple[RequestRow, ...]) -> None:
    """Проверить целостность одной заявки.

    Args:
        requests: Проверенные по схеме строки.

    Raises:
        InputError: Заявка пуста, содержит несколько ID или повтор номера строки.
    """
    if not requests:
        message = "Заявка не содержит строк."
        raise InputError(message)
    if len({row.request_id for row in requests}) != 1:
        message = "Один запуск обрабатывает одну заявку: найдены разные request_id."
        raise InputError(message)
    _require_unique(tuple(row.line for row in requests), "номер строки заявки")


def _validate_price(prices: tuple[PriceRow, ...]) -> None:
    """Проверить ключи и согласованность единиц прайса.

    Args:
        prices: Проверенные по схеме товары.

    Raises:
        InputError: Прайс пуст, SKU повторяется или штука содержит не одну штуку.
    """
    _require_unique(tuple(row.sku for row in prices), "артикул прайса")
    invalid = tuple(
        row.sku for row in prices if row.unit == "шт" and row.pack_size != 1
    )
    if invalid:
        message = f"Для единицы «шт» pack_size должен быть 1: {', '.join(invalid)}."
        raise InputError(message)


def _name(value: str) -> str:
    """Нормализовать регистр и пробелы без изменения смысла названия.

    Args:
        value: Исходное название.

    Returns:
        Название для точного сравнения.
    """
    return " ".join(value.casefold().split())


def _tokens(value: str) -> frozenset[str]:
    """Выделить слова для поиска кандидатов на уточнение.

    Args:
        value: Название покупателя или товара.

    Returns:
        Набор слов; совпадение не является разрешением на продажу.
    """
    return frozenset(re.findall(r"\w+", _name(value)))


def _calculate_line(
    request: RequestRow, product: Product, discount_percent: Decimal
) -> QuoteLine:
    """Рассчитать выбранный товар либо объяснить препятствие.

    Args:
        request: Строка заявки в штуках.
        product: Однозначно выбранная строка прайса.
        discount_percent: Скидка в процентах.

    Returns:
        Расчёт или нерешённая строка с выбранным товаром.
    """
    sale_quantity, remainder = divmod(request.quantity, product.pack_size)
    if remainder:
        return QuoteLine(
            request=request,
            selected=product,
            status=Status.QUANTITY_MISMATCH,
            note=(
                f"{request.quantity} шт. не делятся на упаковки по "
                f"{product.pack_size} шт. Согласуйте количество; оно не увеличено."
            ),
        )
    if product.price is None:
        return QuoteLine(
            request=request,
            selected=product,
            sale_quantity=sale_quantity,
            status=Status.MISSING_PRICE,
            note="Товар найден, цена отсутствует. Запросите цену у поставщика.",
        )
    discounted = money(product.price * (1 - discount_percent / 100))
    multiplier = (
        1 + product.vat_rate / 100 if product.price_basis == "net" else Decimal(1)
    )
    unit_gross = money(discounted * multiplier)
    total = money(unit_gross * sale_quantity)
    return QuoteLine(
        request=request,
        selected=product,
        sale_quantity=sale_quantity,
        discounted_price=discounted,
        unit_price_with_vat=unit_gross,
        total_with_vat=total,
        vat_amount=money(total * product.vat_rate / (100 + product.vat_rate)),
        status=Status.CONFIRMED,
        note="Товар и цена найдены в учебном прайсе; строка рассчитана.",
    )


def _from_sku(
    request: RequestRow, index: dict[str, Product], discount: Decimal
) -> QuoteLine:
    """Использовать указанный артикул без подмены поиском по названию.

    Args:
        request: Строка с непустым SKU.
        index: Прайс с проверенными уникальными артикулами.
        discount: Скидка в процентах.

    Returns:
        Выбранный товар или отдельный статус отсутствия.
    """
    product = index.get(request.sku)
    if product is None:
        return QuoteLine(
            request=request,
            status=Status.NOT_FOUND,
            note=f"Артикула {request.sku} нет в прайсе. Уточните товар или поставщика.",
        )
    return _calculate_line(request, product, discount)


def _from_name(
    request: RequestRow, prices: tuple[Product, ...], discount: Decimal
) -> QuoteLine:
    """Отделить точное название от кандидатов, требующих уточнения.

    Args:
        request: Строка без артикула.
        prices: Товары прайса.
        discount: Скидка в процентах.

    Returns:
        Расчёт только при единственном полном совпадении названия.
    """
    exact = tuple(row for row in prices if _name(row.name) == _name(request.name))
    if len(exact) == 1:
        return _calculate_line(request, exact[0], discount)
    query = _tokens(request.name)
    candidates = exact or tuple(
        row for row in prices if query and query <= _tokens(row.name)
    )
    if candidates:
        return QuoteLine(
            request=request,
            candidates=tuple(sorted(candidates, key=lambda row: row.sku)),
            status=Status.NEEDS_CLARIFICATION,
            note="Уточните артикул или характеристики. Кандидаты не включены в сумму.",
        )
    return QuoteLine(
        request=request,
        status=Status.NOT_FOUND,
        note="Товар не найден по названию. Запросите точный артикул.",
    )


def build_quote(
    requests: tuple[RequestRow, ...],
    prices: tuple[PriceRow, ...],
    *,
    discount_percent: Decimal = Decimal("10"),
) -> Quote:
    """Собрать черновик, сохранив все нерешённые строки.

    Args:
        requests: Одна заявка, количество в штуках.
        prices: Проверенный прайс, цена за единицу продажи.
        discount_percent: Скидка от 0 до 100 процентов включительно.

    Returns:
        Черновик с подытогом подтверждённых строк.

    Raises:
        InputError: Нарушена целостность данных или некорректна скидка.
    """
    _validate_request(requests)
    _validate_price(prices)
    if not discount_percent.is_finite() or not 0 <= discount_percent <= 100:
        message = "Скидка должна быть конечным числом от 0 до 100 процентов."
        raise InputError(message)
    products = tuple(as_product(row) for row in prices)
    index = {row.sku: row for row in products}
    lines = tuple(
        _from_sku(row, index, discount_percent)
        if row.sku
        else _from_name(row, products, discount_percent)
        for row in requests
    )
    confirmed = tuple(line for line in lines if line.status == Status.CONFIRMED)
    return Quote(
        request_id=requests[0].request_id,
        lines=lines,
        discount_percent=discount_percent,
        confirmed_count=len(confirmed),
        unresolved_count=len(lines) - len(confirmed),
        is_complete=len(confirmed) == len(lines),
        subtotal_with_vat=sum(
            (
                line.total_with_vat
                for line in confirmed
                if line.total_with_vat is not None
            ),
            Decimal("0.00"),
        ),
        vat_amount=sum(
            (line.vat_amount for line in confirmed if line.vat_amount is not None),
            Decimal("0.00"),
        ),
    )


def as_product(row: PriceRow) -> Product:
    """Сохранить сущность товара либо обернуть строку для чистого расчёта."""
    if isinstance(row, Product):
        return row
    return Product.model_validate({**row.model_dump(), "id": row.sku, "updated_at": ""})
