import json
import re

from fastapi import HTTPException

from .ports import TicketModel
from .schemas import OrderData, TicketInput

ORDER_FORMAT = re.compile(r"^#\d{6}$")


def extract(ticket: TicketInput, model: TicketModel) -> OrderData:
    data = json.loads(model.complete("helpdesk-extract", "extract", ticket.text))
    order_number = data.get("order_number")
    if order_number is not None and not ORDER_FORMAT.match(order_number):
        raise HTTPException(status_code=502, detail="Número de pedido em formato inválido")
    return OrderData(ticket_id=ticket.ticket_id, order_number=order_number, product=data.get("product"))
