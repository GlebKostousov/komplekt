"""Вырезать секреты и маскировать почту до записи журнала."""

import logging

from structlog.types import EventDict

from ._const import EMAIL_LOG_FIELDS, FORBIDDEN_LOG_FIELDS

__all__ = ["drop_forbidden_fields", "mask_email"]


def mask_email(value: str) -> str:
    """Скрыть почту, оставив два знака имени и один знак домена.

    Args:
        value: Исходный адрес.

    Returns:
        Короткий вид ``iv***@e***`` либо ``***``, если адреса нет.
    """
    if "@" not in value:
        return "***"
    local, _, domain = value.partition("@")
    local_part = local[:2] if len(local) >= 2 else local[:1]
    domain_part = domain[:1]
    return f"{local_part}***@{domain_part}***"


def drop_forbidden_fields(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: EventDict,
) -> EventDict:
    """Убрать запрещённые поля на всех уровнях вложенности.

    Args:
        logger: Журнал stdlib, процессору не нужен.
        method_name: Имя уровня, процессору не нужно.
        event_dict: Поля события до отрисовки.

    Returns:
        Копия события без секретов и с маской почты.
    """
    return {
        key: _apply(key, value)
        for key, value in event_dict.items()
        if key.casefold() not in FORBIDDEN_LOG_FIELDS
    }


def _apply(key: str, value: object) -> object:
    """Замаскировать почту или обойти вложенный словарь и список.

    Args:
        key: Имя поля.
        value: Значение поля.

    Returns:
        Безопасное значение для журнала.
    """
    if key.casefold() in EMAIL_LOG_FIELDS and isinstance(value, str):
        return mask_email(value)
    return _scrub(value)


def _scrub(value: object) -> object:
    """Обойти вложенные контейнеры.

    Args:
        value: Скаляр, словарь или список.

    Returns:
        Копия без запрещённых ключей.
    """
    if isinstance(value, dict):
        return {
            key: _apply(str(key), item)
            for key, item in value.items()
            if str(key).casefold() not in FORBIDDEN_LOG_FIELDS
        }
    if isinstance(value, list | tuple):
        return [_scrub(item) for item in value]
    return value
