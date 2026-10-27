"""Возвращать понятные ошибки и ограничивать входящие запросы."""

from collections.abc import Mapping
from typing import cast
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.domain import Issue, QuoteError
from app.logging import get_logger

LABELS = {
    "revision": "Данные страницы",
    "price": "Цена",
    "source": "Источник цены",
    "discount_percent": "Скидка",
    "company_name": "Название покупателя",
    "inn": "ИНН",
    "kpp": "КПП",
    "ogrn": "ОГРН",
    "address": "Адрес",
    "contact_name": "Контактное лицо",
    "email": "Электронная почта",
    "phone": "Телефон",
    "bank_name": "Банк",
    "bik": "БИК",
    "account": "Расчётный счёт",
    "correspondent_account": "Корреспондентский счёт",
    "file": "Файл",
    "buyer": "Реквизиты покупателя",
    "lines": "Строки заявки",
    "product_id": "Товар",
    "request_id": "Номер заявки",
    "token": "Загрузка",
    "allow_incomplete": "Подтверждение черновика",
}


def _detail(error: Mapping[str, object]) -> str:
    """Использовать собственный русский текст или объяснить ограничение поля."""
    message = str(error.get("msg", ""))
    if message.startswith("Value error, "):
        return message.removeprefix("Value error, ")
    return _constraint(str(error.get("type", "")), error.get("ctx"))


def _constraint(kind: str, context: object) -> str:
    """Перевести стандартные ошибки схемы без выдачи внутренних типов."""
    messages = {
        "missing": "Заполните это поле.",
        "extra_forbidden": "Это поле не поддерживается. Обновите страницу.",
        "string_type": "Введите текст, а не число или список.",
        "int_type": "Укажите целое число.",
        "int_parsing": "Укажите целое число.",
        "bool_type": "Подтвердите действие с помощью кнопки в приложении.",
        "string_pattern_mismatch": "Значение имеет неверный формат. Проверьте его.",
        "json_invalid": "Не удалось прочитать отправленные данные. Повторите действие.",
    }
    if kind == "string_too_long" and isinstance(context, dict):
        return f"Сократите текст до {context.get('max_length')} знаков."
    return messages.get(kind, "Проверьте значение: оно не соответствует формату поля.")


def _issue(error: Mapping[str, object]) -> Issue:
    """Сопоставить ошибку с полем формы, не возвращая секретные внутренние данные."""
    location = cast(tuple[str | int, ...], error.get("loc", ()))
    fields = tuple(
        str(part) for part in location if part not in {"body", "path", "query"}
    )
    key = fields[-1] if fields else ""
    label = LABELS.get(key, key or "Данные")
    return Issue(
        row=None,
        field=".".join(fields) or None,
        value=None,
        message=f"{label}: {_detail(error)}",
    )


async def _validation_handler(
    request: Request, error: RequestValidationError | ValidationError
) -> JSONResponse:
    """Отдать все найденные ошибки формы понятным списком."""
    del request
    issues = tuple(_issue(item) for item in error.errors())
    return JSONResponse(
        status_code=422,
        content={
            "code": "INVALID_INPUT",
            "message": "Проверьте отмеченные поля.",
            "issues": [issue.model_dump(mode="json") for issue in issues],
        },
    )


async def _domain_handler(request: Request, error: QuoteError) -> JSONResponse:
    """Отдать публичный текст и записать внутренний в журнал.

    Args:
        request: Входящий запрос. Тело в журнал не пишется.
        error: Ожидаемая ошибка приложения.

    Returns:
        Безопасный JSON со статусом самой ошибки.
    """
    del request
    _log_domain(error)
    return JSONResponse(
        status_code=error.http_status,
        content={
            "code": error.code,
            "message": error.public_message,
            "issues": [issue.model_dump(mode="json") for issue in error.issues],
        },
        headers=error.headers,
    )


def _log_domain(error: QuoteError) -> None:
    """Записать код и внутренний текст без тела запроса.

    Args:
        error: Ожидаемая ошибка.
    """
    logger = get_logger(__name__)
    if error.http_status >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "app.domain_error",
            code=error.code,
            status_code=error.http_status,
            detail=error.internal_message,
        )
        return
    logger.warning(
        "app.domain_error",
        code=error.code,
        status_code=error.http_status,
        detail=error.internal_message,
    )


async def _unexpected_handler(request: Request, error: Exception) -> JSONResponse:
    """Скрыть непойманный сбой за безопасным JSON.

    Args:
        request: Входящий запрос.
        error: Неожиданное исключение.

    Returns:
        Ответ 500 без внутренних подробностей.
    """
    del request, error
    get_logger(__name__).exception("app.unhandled")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_ERROR",
            "message": "Не удалось выполнить действие. Повторите его ещё раз.",
            "issues": [],
        },
    )


async def _http_handler(request: Request, error: HTTPException) -> JSONResponse:
    """Скрыть стандартные англоязычные ответы веб-фреймворка."""
    del request
    messages = {
        400: "Не удалось прочитать запрос. Выберите файл или заполните форму ещё раз.",
        404: "Страница или файл не найдены. Вернитесь в приложение.",
        405: "Это действие не поддерживается. Обновите страницу.",
        413: "Файл слишком большой. Разрешён CSV размером не больше 1 МБ.",
    }
    return JSONResponse(
        status_code=error.status_code,
        content={
            "code": "REQUEST_ERROR",
            "message": messages.get(
                error.status_code,
                "Не удалось выполнить действие. "
                "Обновите страницу и попробуйте ещё раз.",
            ),
            "issues": [],
        },
    )


def add_error_handlers(app: FastAPI) -> None:
    """Подключить обработчики ожидаемых ошибок без общего подавления исключений."""
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(QuoteError, _domain_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unexpected_handler)


class RequestContext:
    """Привязать номер запроса к журналу на время обработки."""

    def __init__(self, app: ASGIApp) -> None:
        """Сохранить вложенное приложение.

        Args:
            app: Следующий обработчик.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Очистить контекст после HTTP-запроса.

        Args:
            scope: ASGI-область.
            receive: Канал входящих сообщений.
            send: Канал исходящих сообщений.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=uuid4().hex)
        try:
            await self.app(scope, receive, send)
        finally:
            structlog.contextvars.clear_contextvars()


class RequestGuard:
    """Ограничить размер тела и отсеять изменения с чужих веб-страниц."""

    def __init__(self, app: ASGIApp) -> None:
        """Сохранить вложенное приложение."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Проверять только изменяющие HTTP-запросы."""
        mutating = scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}
        if scope["type"] == "http" and mutating:
            await self._guard(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def _guard(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Требовать служебный заголовок, который чужой сайт не отправит без CORS."""
        headers = dict(scope["headers"])
        if headers.get(b"x-komplekt-request") != b"1":
            response = JSONResponse(
                status_code=403,
                content={
                    "code": "REQUEST_ORIGIN",
                    "message": "Откройте приложение и повторите действие.",
                    "issues": [],
                },
            )
            await response(scope, receive, send)
            return
        await self._bounded(scope, receive, send)

    async def _bounded(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Буферизовать ограниченное тело до разбора multipart или JSON."""
        limit = 1_048_576 + 65_536 if scope["path"].endswith("/preview") else 65_536
        body = await _read_body(receive, limit)
        if body is None:
            response = JSONResponse(
                status_code=413,
                content={
                    "code": "TOO_LARGE",
                    "message": "Слишком много данных. Файл должен быть не больше 1 МБ.",
                    "issues": [],
                },
            )
            await response(scope, receive, send)
            return

        async def replay() -> Message:
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


async def _read_body(receive: Receive, limit: int) -> bytes | None:
    """Не читать произвольный файл целиком в память."""
    result = bytearray()
    more = True
    while more:
        message = await receive()
        result.extend(message.get("body", b""))
        if len(result) > limit:
            return None
        more = message.get("more_body", False)
    return bytes(result)


class SecurityHeaders:
    """Запретить выполнение загруженного содержимого и внешние ресурсы интерфейса."""

    def __init__(self, app: ASGIApp) -> None:
        """Сохранить вложенное приложение."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Добавить заголовки без изменения содержимого ответа."""

        async def guarded_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_security_headers())
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, guarded_send)


def _security_headers() -> list[tuple[bytes, bytes]]:
    """Не загружать скрипты, шрифты и картинки с внешних сервисов."""
    return [
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"same-origin"),
        (b"cache-control", b"no-store"),
        (
            b"content-security-policy",
            b"default-src 'self'; script-src 'self'; "
            b"style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; "
            b"object-src 'none'; frame-src 'self'; base-uri 'self'; "
            b"frame-ancestors 'self'",
        ),
    ]
