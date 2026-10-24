from .ports import TicketModel
from .schemas import ReplySuggestion, TicketInput


def suggest(ticket: TicketInput, model: TicketModel) -> ReplySuggestion:
    text = model.complete("helpdesk-suggest", "suggest", ticket.text)
    return ReplySuggestion(ticket_id=ticket.ticket_id, suggestion=text)
