import json
import os
from datetime import date, datetime

from fastapi import HTTPException

from .ports import TicketModel
from .schemas import PeriodInput, Topic, TopicsReport

TICKETS_FILE = os.environ.get("TICKETS_FILE", "/data/tickets.jsonl")
TICKETS_PER_CALL = 150


def _in_period(start: date, end: date) -> list[dict]:
    selected = []
    with open(TICKETS_FILE, encoding="utf-8") as file:
        for line in file:
            ticket = json.loads(line)
            day = datetime.fromisoformat(ticket["created_at"]).date()
            if start <= day <= end:
                selected.append(ticket)
    return selected


def topics(period: PeriodInput, model: TicketModel, on_progress=None) -> TopicsReport:
    if period.start > period.end:
        raise HTTPException(status_code=422, detail="A data inicial é posterior à data final")

    selected = _in_period(period.start, period.end)
    if on_progress is not None:
        on_progress(0, len(selected))

    totals: dict[str, dict] = {}
    processed = 0
    for first in range(0, len(selected), TICKETS_PER_CALL):
        batch = selected[first:first + TICKETS_PER_CALL]
        content = "\n".join(f"[{ticket['id']}] {ticket['text']}" for ticket in batch)
        answer = json.loads(model.complete("helpdesk-topics", "topics", content))
        for item in answer["topics"]:
            current = totals.setdefault(item["topic"], {"count": 0, "examples": []})
            current["count"] += item["count"]
            current["examples"] = (current["examples"] + item["examples"])[:3]
        processed += len(batch)
        if on_progress is not None:
            on_progress(processed, len(selected))

    items = [Topic(topic=name, **data) for name, data in totals.items()]
    items.sort(key=lambda topic: (-topic.count, topic.topic))
    return TopicsReport(start=period.start, end=period.end, total_tickets=len(selected), topics=items)
