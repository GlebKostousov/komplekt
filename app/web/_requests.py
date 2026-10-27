"""Сохранять явные решения пользователя по текущей заявке."""

from app.domain import BuyerDraft, InputError, Product
from app.storage import Repository, Transaction

from ._commands import (
    ChooseProduct,
    EditBuyer,
    EditDiscount,
    EditPrice,
    SaveDraft,
    SelectLines,
)
from ._state import timestamp


def edit_price(repository: Repository, product_id: str, command: EditPrice) -> None:
    """Изменить цену одной сущности, общую для всех черновиков."""
    with repository.write(command.revision) as transaction:
        product = transaction.product(product_id)
        updated = Product.model_validate(
            {
                **product.model_dump(),
                "price": command.price,
                "source": command.source,
                "updated_at": timestamp(),
            }
        )
        transaction.save_product(updated)


def edit_buyer(repository: Repository, request_id: str, command: EditBuyer) -> None:
    """Сохранить проверенную форму покупателя вместе с заявкой."""
    with repository.write(command.revision) as transaction:
        request = transaction.request(request_id)
        transaction.save_request(
            request.model_copy(
                update={
                    "buyer": command.buyer,
                    "buyer_draft": BuyerDraft.model_validate(
                        command.buyer.model_dump()
                    ),
                }
            )
        )


def select_lines(repository: Repository, request_id: str, command: SelectLines) -> None:
    """Разрешить выбирать только реальные строки этой заявки."""
    with repository.write(command.revision) as transaction:
        request = transaction.request(request_id)
        available = {row.line for row in request.rows}
        selected = set(command.lines)
        if len(selected) != len(command.lines) or not selected <= available:
            raise InputError("Выберите каждую строку заявки не больше одного раза.")
        transaction.save_request(
            request.model_copy(
                update={
                    "selected_lines": tuple(
                        row.line for row in request.rows if row.line in selected
                    )
                }
            )
        )


def choose_product(
    repository: Repository, request_id: str, line: int, command: ChooseProduct
) -> None:
    """Сохранить выбор человека, не переписывая исходную строку покупателя."""
    with repository.write(command.revision) as transaction:
        request = transaction.request(request_id)
        if line not in {row.line for row in request.rows}:
            raise InputError("В этой заявке нет такой строки. Обновите страницу.")
        choices = dict(request.choices)
        _update_choice(transaction, choices, line, command.product_id)
        transaction.save_request(request.model_copy(update={"choices": choices}))


def _update_choice(
    transaction: Transaction, choices: dict[str, str], line: int, product_id: str | None
) -> None:
    """Проверить текущий товар либо убрать ручной выбор."""
    if product_id is None:
        choices.pop(str(line), None)
        return
    transaction.product(product_id)
    choices[str(line)] = product_id


def edit_discount(
    repository: Repository, request_id: str, command: EditDiscount
) -> None:
    """Применить проверенную скидку к будущим расчётам заявки."""
    with repository.write(command.revision) as transaction:
        request = transaction.request(request_id)
        transaction.save_request(
            request.model_copy(
                update={
                    "discount_percent": command.discount_percent,
                    "discount_draft": format(command.discount_percent, "f"),
                }
            )
        )


def save_draft(repository: Repository, request_id: str, command: SaveDraft) -> None:
    """Сохранить незаконченную форму, не проверяя контрольные суммы.

    Args:
        repository: Хранилище.
        request_id: Номер заявки.
        command: Черновик реквизитов и текст скидки.
    """
    with repository.write(command.revision) as transaction:
        request = transaction.request(request_id)
        transaction.save_request(
            request.model_copy(
                update={
                    "buyer_draft": command.buyer_draft,
                    "discount_draft": command.discount_draft,
                }
            )
        )
