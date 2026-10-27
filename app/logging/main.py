"""Структурный журнал: JSON в production, консоль в разработке."""

import logging
import os
import sys
from typing import TextIO, cast

import structlog

from ._const import EMAIL_LOG_FIELDS, FORBIDDEN_LOG_FIELDS
from ._sanitize import drop_forbidden_fields, mask_email

__all__ = [
    "EMAIL_LOG_FIELDS",
    "FORBIDDEN_LOG_FIELDS",
    "drop_forbidden_fields",
    "get_logger",
    "mask_email",
    "setup_logging",
]


def setup_logging() -> None:
    """Настроить журнал один раз при сборке приложения.

    ``KOMPLEKT_LOG_OUTPUT=json`` включает JSON. Иначе консоль.
    ``KOMPLEKT_LOG_LEVEL`` задаёт уровень, по умолчанию INFO.
    """
    if any(isinstance(item, _MarkedStreamHandler) for item in logging.root.handlers):
        return
    level_name = os.environ.get("KOMPLEKT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    output = os.environ.get("KOMPLEKT_LOG_OUTPUT", "console")
    processors = _processors(output)
    renderer = _renderer(output)
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=processors,
    )
    handler = _MarkedStreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(handlers=[handler], level=level, force=True)
    for name in ("uvicorn.access", "uvicorn.error", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


class _MarkedStreamHandler(logging.StreamHandler[TextIO]):
    """Поток stdout, по которому повторная настройка журнала узнаёт себя."""

    def __init__(self) -> None:
        """Писать журнал в стандартный вывод."""
        super().__init__(sys.stdout)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Вернуть журналировщик модуля.

    Args:
        name: Обычно ``__name__``.

    Returns:
        Связанный структурный журналировщик.
    """
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def _processors(output: str) -> list[structlog.types.Processor]:
    """Собрать общую цепочку до отрисовки.

    Args:
        output: ``json`` добавляет текст исключения в событие.

    Returns:
        Процессоры structlog.
    """
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    if output == "json":
        processors.append(structlog.processors.format_exc_info)
    processors.append(drop_forbidden_fields)
    return processors


def _renderer(output: str) -> structlog.types.Processor:
    """Выбрать JSON или консоль.

    Args:
        output: ``json`` либо любое другое значение для консоли.

    Returns:
        Процессор отрисовки.
    """
    if output == "json":
        return structlog.processors.JSONRenderer(ensure_ascii=False)
    return structlog.dev.ConsoleRenderer(colors=True)
