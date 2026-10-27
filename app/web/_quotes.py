"""Выпускать неизменяемые PDF из проверенного состояния данных."""

from uuid import uuid4

from app.documents import default_seller, render_pdf
from app.domain import (
    Draft,
    InputError,
    QuoteSummary,
    SavedQuote,
    Schema,
    State,
    build_draft,
)
from app.storage import Repository, Transaction

from ._commands import CreateQuote
from ._state import read_state, timestamp


class Calculation(Schema):
    """Расчёт и номер прочитанного состояния для проверки перед выпуском."""

    revision: int
    quote: Draft


class CreatedQuote(Schema):
    """Вернуть новую запись в истории и готовую ссылку на документ."""

    state: State
    quote_id: str


def calculation(repository: Repository, request_id: str) -> Calculation:
    """Считать по текущим товарам; ранее выпущенные документы не трогать."""
    with repository.read() as transaction:
        return Calculation(
            revision=transaction.revision(),
            quote=build_draft(transaction.request(request_id), transaction.catalog()),
        )


def _check_draft(draft: Draft, allow_incomplete: bool) -> None:
    """Не выпускать пустой документ или незаметно неполное предложение."""
    if not draft.selected_count:
        raise InputError("Для КП выберите хотя бы одну строку из заявки.")
    if not draft.is_complete and not allow_incomplete:
        raise InputError(
            "Не все данные заполнены. Проверьте нерешённые позиции и реквизиты "
            "покупателя. Можно продолжить только с пометкой «Черновик»."
        )


def _summary(document: SavedQuote) -> QuoteSummary:
    """Подготовить строку истории из того же снимка, что попадёт в PDF."""
    quote = document.quote
    return QuoteSummary(
        id=document.id,
        number=document.number,
        created_at=document.created_at,
        request_id=quote.request_id,
        buyer_name=quote.buyer.company_name or "Не указан",
        subtotal_with_vat=quote.subtotal_with_vat,
        vat_amount=quote.vat_amount,
        is_complete=quote.is_complete,
        selected_count=quote.selected_count,
        unresolved_count=quote.unresolved_count,
        filename=f"KP-{document.number}-{quote.request_id}.pdf",
    )


def create_quote(
    repository: Repository, command: CreateQuote, idempotency_key: str
) -> CreatedQuote:
    """Сохранить расчёт и PDF. Повтор с тем же ключом возвращает первый документ.

    Args:
        repository: Хранилище.
        command: Заявка и подтверждение неполноты.
        idempotency_key: Ключ одного нажатия «Сохранить КП».

    Returns:
        Состояние и идентификатор документа.
    """
    with repository.write(
        command.revision, idempotency_key=idempotency_key
    ) as transaction:
        quote_id = transaction.replay_id or _issue(
            transaction, command, idempotency_key
        )
    return CreatedQuote(state=read_state(repository), quote_id=quote_id)


def _issue(transaction: Transaction, command: CreateQuote, idempotency_key: str) -> str:
    """Выпустить новый документ внутри уже открытой транзакции.

    Args:
        transaction: Транзакция записи.
        command: Заявка и подтверждение неполноты.
        idempotency_key: Ключ повтора.

    Returns:
        Идентификатор нового документа.
    """
    draft = build_draft(transaction.request(command.request_id), transaction.catalog())
    _check_draft(draft, command.allow_incomplete)
    document = SavedQuote(
        id=uuid4().hex,
        number=f"{transaction.next_number():04d}",
        created_at=timestamp(),
        seller=default_seller(),
        quote=draft,
    )
    transaction.save_quote(
        document, _summary(document), render_pdf(document), idempotency_key
    )
    return document.id
