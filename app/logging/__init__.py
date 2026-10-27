"""Фасад структурного журнала."""

from .main import (
    EMAIL_LOG_FIELDS,
    FORBIDDEN_LOG_FIELDS,
    drop_forbidden_fields,
    get_logger,
    mask_email,
    setup_logging,
)

__all__ = [
    "EMAIL_LOG_FIELDS",
    "FORBIDDEN_LOG_FIELDS",
    "drop_forbidden_fields",
    "get_logger",
    "mask_email",
    "setup_logging",
]
