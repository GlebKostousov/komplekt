"""Ожидаемые ошибки с кодом, статусом и двумя текстами."""

from typing import ClassVar

from fastapi import status

from ._schema import Issue


class QuoteError(Exception):
    """Корень прикладных ошибок. Клиент видит только публичный текст.

    Attributes:
        code: Стабильный машинный код ответа.
        http_status: Статус HTTP на границе API.
        public_message: Текст для человека.
        internal_message: Текст для журнала.
        issues: Подробности по полям, если они есть.
        headers: Дополнительные заголовки ответа.
    """

    code: ClassVar[str] = "QUOTE_ERROR"
    http_status: ClassVar[int] = status.HTTP_422_UNPROCESSABLE_CONTENT
    public_message: str = "Проверьте данные и повторите действие."
    headers: ClassVar[dict[str, str] | None] = None

    def __init__(
        self,
        public_message: str | None = None,
        *,
        internal_message: str | None = None,
        issues: tuple[Issue, ...] = (),
    ) -> None:
        """Запомнить публичный текст и отдельно текст журнала.

        Args:
            public_message: Безопасный текст. Если не передан, берётся текст класса.
            internal_message: Полный текст журнала. По умолчанию совпадает с публичным.
            issues: Замечания по строкам и полям.
        """
        if public_message is not None:
            self.public_message = public_message
        self.internal_message = internal_message or self.public_message
        self.issues = issues
        super().__init__(self.internal_message)


class InputError(QuoteError):
    """Сообщить, что введённые данные нельзя принять."""

    code: ClassVar[str] = "INVALID_INPUT"


class OutputError(QuoteError):
    """Сообщить, что результат не удалось записать."""

    code: ClassVar[str] = "OUTPUT_ERROR"
    http_status: ClassVar[int] = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_message = "Не удалось записать результат. Повторите действие."
