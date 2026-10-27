"""Перевести ошибки схемы в понятные замечания к ячейкам."""

from pydantic_core import ErrorDetails

from app.domain import Issue

FIELD_NAMES = {
    "request_id": "Номер заявки",
    "line": "Номер позиции",
    "sku": "Артикул",
    "name": "Наименование",
    "quantity": "Количество",
    "unit": "Единица",
    "pack_size": "Штук в упаковке",
    "price": "Цена",
    "price_basis": "НДС в цене",
    "vat_rate": "Ставка НДС",
    "source": "Источник цены",
}
FIELD_RULES = {
    "request_id": "Укажите номер заявки до 80 знаков: латинские буквы, "
    "цифры, точка, дефис или подчёркивание. Например "
    "REQ-001.",
    "line": "Укажите целый номер позиции от 1 до 1000000, например 1.",
    "sku": "Укажите артикул до 80 знаков: буквы, цифры, дефис, "
    "точка или подчёркивание. Пример A-100. В заявке можно "
    "оставить артикул пустым.",
    "name": "Укажите название от 1 до 300 знаков, например Датчик A.",
    "quantity": "Укажите целое количество от 1 до 1000000, например 2. "
    "Количество заявки всегда в штуках.",
    "unit": "В заявке укажите шт. В прайсе допустимы шт и упак.",
    "pack_size": "Укажите целое число штук от 1 до 1000000. Для единицы шт — только 1.",
    "price": "Укажите цену от 0 до 999999999999,99, не больше двух "
    "знаков после запятой, без ₽. Если цена неизвестна, "
    "оставьте ячейку пустой.",
    "price_basis": "Укажите net, если цена без НДС, или gross, если НДС уже включён.",
    "vat_rate": "В этом учебном примере укажите ставку НДС 20.",
    "source": "Укажите источник цены от 1 до 500 знаков, например "
    "Прайс поставщика от 27.10, строка 5.",
}


def safe_value(value: object) -> str:
    """Ограничить значение для сообщения и показать скрытые символы буквально."""
    text = str(value)
    text = "".join(char if char.isprintable() else repr(char)[1:-1] for char in text)
    return text[:100] + ("…" if len(text) > 100 else "")


def issue_from_error(error: ErrorDetails, row: int) -> Issue:
    """Подсказать исправление поля без внутренних названий исключений."""
    field = str(error["loc"][0]) if error["loc"] else None
    fallback = FIELD_RULES.get(field or "", "Проверьте значения этой строки.")
    description = (
        str(error["ctx"]["error"]) if error.get("ctx", {}).get("error") else fallback
    )
    label = FIELD_NAMES.get(field or "", "Строка")
    value = safe_value(error.get("input", ""))
    return Issue(
        row=row,
        field=field,
        value=value,
        message=f"{_cell_intro(field, label, value)} {description}",
    )


def _cell_intro(field: str | None, label: str, value: str) -> str:
    """Назвать столбец и фактическое значение, чтобы ячейку легко было найти."""
    if field is None:
        return "Проверьте значения этой строки."
    content = f"указано «{value}»" if value else "пустая ячейка"
    return f"В столбце «{label}» ({field}) {content}."
