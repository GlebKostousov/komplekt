"""Проверять загрузки и применять их только после подтверждения."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, TypedDict, cast
from uuid import uuid4

from app.domain import (
    Buyer,
    BuyerDraft,
    Catalog,
    PriceRow,
    Product,
    RequestRecord,
    RequestRow,
)
from app.imports import ParsedUpload, parse_upload
from app.storage import ConflictError, PendingImport, Repository, Transaction

from ._commands import Changes, CommitImport, ImportPreview
from ._state import timestamp


def _price_changes(parsed: ParsedUpload, catalog: Catalog | None) -> Changes:
    """Сравнить состав и цены, включая ранее внесённые ручные правки."""
    before = {product.sku: product for product in catalog.products} if catalog else {}
    after = {
        product.sku: product for product in cast(tuple[PriceRow, ...], parsed.rows)
    }
    shared = before.keys() & after.keys()
    changed = sum(
        before[sku].model_dump(exclude={"id", "updated_at"}) != after[sku].model_dump()
        for sku in shared
    )
    return Changes(
        added=len(after.keys() - before.keys()),
        changed=changed,
        removed=len(before.keys() - after.keys()),
    )


def _changes(parsed: ParsedUpload, transaction: Transaction) -> Changes:
    """Подготовить числа для подтверждения загрузки."""
    if parsed.kind == "price":
        return _price_changes(parsed, transaction.catalog())
    current = transaction.find_request(parsed.request_id or "")
    return Changes(
        added=len(parsed.rows) if current is None else 0,
        changed=len(parsed.rows) if current is not None else 0,
        removed=0,
        replaces_request=current is not None,
    )


def preview_import(
    repository: Repository,
    kind: Literal["price", "request"],
    payload: bytes,
    filename: str,
    content_type: str,
) -> ImportPreview:
    """Проверить весь файл, затем сохранить краткоживущее подтверждение."""
    parsed = parse_upload(kind, payload, filename, content_type)
    expires = (datetime.now(UTC) + timedelta(minutes=30)).isoformat(timespec="seconds")
    with repository.read() as transaction:
        revision = transaction.revision()
        changes = _changes(parsed, transaction)
    pending = PendingImport(
        token=uuid4().hex,
        kind=kind,
        filename=parsed.filename,
        content_type=content_type,
        payload=payload,
        revision=revision,
        expires_at=expires,
    )
    with repository.write(revision, advance=False) as transaction:
        transaction.remember_import(pending, timestamp())
    return ImportPreview(
        token=pending.token,
        revision=revision,
        kind=kind,
        filename=parsed.filename,
        row_count=len(parsed.rows),
        request_id=parsed.request_id,
        rows=parsed.rows[:10],
        warnings=parsed.warnings,
        changes=changes,
        expires_at=expires,
    )


def _catalog(parsed: ParsedUpload) -> Catalog:
    """Создать новые сущности, даже если часть артикулов совпала со старым прайсом."""
    now = timestamp()
    products = tuple(
        Product.model_validate(
            {**row.model_dump(), "id": uuid4().hex, "updated_at": now}
        )
        for row in parsed.rows
    )
    return Catalog(
        generation=uuid4().hex,
        filename=parsed.filename,
        sha256=parsed.sha256,
        uploaded_at=now,
        products=products,
    )


class _Kept(TypedDict):
    """Поля заявки, которые переживают замену файла.

    Attributes:
        buyer: Проверенные реквизиты.
        buyer_draft: Черновик реквизитов, в том числе неполный.
        discount_percent: Сохранённая скидка.
        discount_draft: Текст скидки в форме.
    """

    buyer: Buyer
    buyer_draft: BuyerDraft
    discount_percent: Decimal
    discount_draft: str


def _save_request(parsed: ParsedUpload, transaction: Transaction) -> None:
    """Обновить одну заявку и сохранить введённого ранее покупателя."""
    request_id = parsed.request_id or ""
    current = transaction.find_request(request_id)
    if current is not None and current.sha256 == parsed.sha256:
        return
    rows = cast(tuple[RequestRow, ...], parsed.rows)
    request = RequestRecord(
        request_id=request_id,
        filename=parsed.filename,
        sha256=parsed.sha256,
        uploaded_at=timestamp(),
        rows=rows,
        selected_lines=tuple(row.line for row in rows),
        **_kept(current),
    )
    transaction.save_request(request)


def _kept(current: RequestRecord | None) -> _Kept:
    """Оставить покупателя, скидку и их черновики при замене файла заявки.

    Args:
        current: Прежняя заявка или ``None``.

    Returns:
        Поля, которые новая запись забирает у прежней.
    """
    if current is None:
        return {
            "buyer": Buyer(),
            "buyer_draft": BuyerDraft(),
            "discount_percent": Decimal("10"),
            "discount_draft": "10",
        }
    return {
        "buyer": current.buyer,
        "buyer_draft": current.buyer_draft,
        "discount_percent": current.discount_percent,
        "discount_draft": current.discount_draft,
    }


def commit_import(repository: Repository, command: CommitImport) -> None:
    """Атомарно применить именно тот файл, который прошёл проверку."""
    with repository.write(command.revision) as transaction:
        pending = transaction.pending_import(command.token)
        _check_pending(pending, command.revision)
        parsed = parse_upload(
            pending.kind, pending.payload, pending.filename, pending.content_type
        )
        _apply(parsed, transaction)
        transaction.forget_import(pending.token)


def _check_pending(pending: PendingImport, revision: int) -> None:
    """Не применять устаревшие или повторные подтверждения."""
    if pending.expires_at < timestamp() or pending.revision != revision:
        raise ConflictError(
            "После проверки файла данные изменились или прошло больше 30 минут. "
            "Загрузите файл ещё раз, чтобы увидеть актуальные изменения."
        )


def _apply(parsed: ParsedUpload, transaction: Transaction) -> None:
    """Разделить замену каталога и обновление одной заявки."""
    if parsed.kind == "price":
        transaction.replace_catalog(_catalog(parsed))
    else:
        _save_request(parsed, transaction)
