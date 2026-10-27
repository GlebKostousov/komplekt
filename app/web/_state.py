"""Собирать согласованное состояние приложения из локальной базы."""

from datetime import UTC, datetime

from app.documents import default_seller
from app.domain import State
from app.storage import Repository

ASSUMPTIONS = (
    "Входа нет. Кто открыл это приложение, видит и меняет общие данные. "
    "Реквизиты только вымышленные.",
    "Принимаются CSV в UTF-8 с разделителем «;». Excel и PDF не загружаются.",
    "Новый прайс удаляет прежние товары. Ручные цены и подобранные соответствия "
    "сбрасываются. Выпущенные PDF остаются.",
    "Правка цены сразу входит в расчёт заявок. Уже сохранённый PDF не пересчитывается.",
    "Скидка по умолчанию 10%, НДС 20%, валюта — рубли. Количество в заявке — "
    "в штуках, продажа — целыми упаковками.",
    "Продавец, предмет и условия заданы в примере. КП покупателю само не отправляется.",
)


def timestamp() -> str:
    """Получить однозначное время для хранения; интерфейс покажет московское."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def read_state(repository: Repository) -> State:
    """Вернуть текущее состояние одним согласованным чтением."""
    with repository.read() as transaction:
        return State(
            revision=transaction.revision(),
            catalog=transaction.catalog(),
            requests=transaction.requests(),
            quotes=transaction.summaries(),
            seller=default_seller(),
            assumptions=ASSUMPTIONS,
        )
