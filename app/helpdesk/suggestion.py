from collections.abc import Iterator

from .ports import TicketModel
from .schemas import TicketInput


def suggest(ticket: TicketInput, model: TicketModel) -> Iterator[str]:
    yield from model.stream("helpdesk-suggest", "suggest", ticket.text)
