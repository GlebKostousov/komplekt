"""Собрать HTTP-маршруты локального приложения."""

from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, FastAPI, File, Header, UploadFile
from fastapi import Path as PathParam
from starlette.responses import Response

from app.domain import SavedQuote, State
from app.imports import MAX_BYTES
from app.storage import Repository

from ._commands import (
    ChooseProduct,
    CommitImport,
    CreateQuote,
    EditBuyer,
    EditDiscount,
    EditPrice,
    ImportPreview,
    SaveDraft,
    SelectLines,
)
from ._http import RequestContext, RequestGuard, SecurityHeaders, add_error_handlers
from ._imports import commit_import, preview_import
from ._quotes import Calculation, CreatedQuote, calculation, create_quote
from ._requests import (
    choose_product,
    edit_buyer,
    edit_discount,
    edit_price,
    save_draft,
    select_lines,
)
from ._state import read_state

IdPath = Annotated[str, PathParam(pattern=r"^[a-f0-9]{32}$")]
RequestPath = Annotated[str, PathParam(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")]
LinePath = Annotated[int, PathParam(gt=0, le=1_000_000)]


def create_router(repository: Repository, examples: Path) -> APIRouter:
    """Передать конкретное хранилище всем маршрутам без глобального состояния."""
    router = APIRouter(prefix="/api")
    _read_routes(router, repository)
    _example_route(router, examples)
    _import_routes(router, repository)
    _edit_routes(router, repository)
    _selection_route(router, repository)
    _quote_routes(router, repository)
    _document_routes(router, repository)
    return router


def configure_http(app: FastAPI) -> None:
    """Подключить входные ограничения и понятные ошибки через фасад пакета."""
    add_error_handlers(app)
    app.add_middleware(RequestGuard)
    app.add_middleware(SecurityHeaders)
    app.add_middleware(RequestContext)


def _read_routes(router: APIRouter, repository: Repository) -> None:
    """Добавить чтение состояния и исходных образцов."""

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "application": "komplekt", "version": "1.0.0"}

    @router.get("/state")
    def state() -> State:
        return read_state(repository)


def _example_route(router: APIRouter, examples: Path) -> None:
    """Отдать исходные учебные CSV с меткой кодировки для Excel."""

    @router.get("/examples/{kind}.csv")
    def example(kind: Literal["request", "price"]) -> Response:
        content = (examples / f"{kind}.csv").read_bytes().removeprefix(b"\xef\xbb\xbf")
        return Response(
            content=b"\xef\xbb\xbf" + content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'},
        )


def _import_routes(router: APIRouter, repository: Repository) -> None:
    """Отделить проверку файла от замены данных."""

    @router.post("/imports/{kind}/preview")
    async def preview(
        kind: Literal["price", "request"], file: Annotated[UploadFile, File()]
    ) -> ImportPreview:
        try:
            payload = await file.read(MAX_BYTES + 1)
            return preview_import(
                repository,
                kind,
                payload,
                file.filename or "",
                file.content_type or "application/octet-stream",
            )
        finally:
            await file.close()

    @router.post("/imports/commit")
    def commit(command: CommitImport) -> State:
        commit_import(repository, command)
        return read_state(repository)


def _edit_routes(router: APIRouter, repository: Repository) -> None:
    """Добавить правку цен, реквизитов и выбранных строк."""

    @router.patch("/products/{product_id}")
    def price(product_id: IdPath, command: EditPrice) -> State:
        edit_price(repository, product_id, command)
        return read_state(repository)

    @router.patch("/requests/{request_id}/buyer")
    def buyer(request_id: RequestPath, command: EditBuyer) -> State:
        edit_buyer(repository, request_id, command)
        return read_state(repository)

    _draft_route(router, repository)
    _choice_routes(router, repository)


def _draft_route(router: APIRouter, repository: Repository) -> None:
    """Сохранять незаконченную форму отдельно от проверенных реквизитов."""

    @router.patch("/requests/{request_id}/draft")
    def draft(request_id: RequestPath, command: SaveDraft) -> State:
        save_draft(repository, request_id, command)
        return read_state(repository)


def _selection_route(router: APIRouter, repository: Repository) -> None:
    """Обновить состав позиций будущего предложения."""

    @router.put("/requests/{request_id}/selection")
    def selection(request_id: RequestPath, command: SelectLines) -> State:
        select_lines(repository, request_id, command)
        return read_state(repository)


def _choice_routes(router: APIRouter, repository: Repository) -> None:
    """Добавить явный выбор соответствия и проверенную скидку."""

    @router.put("/requests/{request_id}/choices/{line}")
    def choice(
        request_id: RequestPath, line: LinePath, command: ChooseProduct
    ) -> State:
        choose_product(repository, request_id, line, command)
        return read_state(repository)

    @router.patch("/requests/{request_id}/discount")
    def discount(request_id: RequestPath, command: EditDiscount) -> State:
        edit_discount(repository, request_id, command)
        return read_state(repository)


def _quote_routes(router: APIRouter, repository: Repository) -> None:
    """Считать текущий черновик и читать выпущенные неизменяемые документы."""

    @router.get("/requests/{request_id}/calculation")
    def calculate(request_id: RequestPath) -> Calculation:
        return calculation(repository, request_id)

    @router.post("/quotes")
    def create(
        command: CreateQuote,
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", pattern=r"^[a-f0-9]{32}$")
        ],
    ) -> CreatedQuote:
        return create_quote(repository, command, idempotency_key)


def _document_routes(router: APIRouter, repository: Repository) -> None:
    """Вернуть снимок данных или точный сохранённый PDF."""

    @router.get("/quotes/{quote_id}")
    def snapshot(quote_id: IdPath) -> SavedQuote:
        with repository.read() as transaction:
            return transaction.quote(quote_id)

    @router.get("/quotes/{quote_id}/pdf")
    def pdf(quote_id: IdPath, inline: bool = False) -> Response:
        with repository.read() as transaction:
            filename, content = transaction.pdf(quote_id)
        mode = "inline" if inline else "attachment"
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'{mode}; filename="{filename}"',
            },
        )
