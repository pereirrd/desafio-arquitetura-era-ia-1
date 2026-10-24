import json
from threading import Thread
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import classification, extraction, report, suggestion
from .gateway import ModelUnavailable, build_client
from .schemas import Classification, OrderData, PeriodInput, TicketInput

app = FastAPI(title="Helpdesk")
model = build_client()
jobs: dict[str, dict] = {}


@app.exception_handler(ModelUnavailable)
def model_unavailable(_request, error: ModelUnavailable):
    return JSONResponse(status_code=502, content={"detail": str(error)})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/tickets/classification")
def classify_ticket(ticket: TicketInput) -> Classification:
    return classification.classify(ticket, model)


@app.post("/tickets/reply-suggestion")
def suggest_reply(ticket: TicketInput):
    def events():
        try:
            for piece in suggestion.suggest(ticket, model):
                payload = json.dumps({"chunk": piece}, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            end = json.dumps({"ticket_id": ticket.ticket_id})
            yield f"event: end\ndata: {end}\n\n"
        except Exception:
            failure = json.dumps(
                {"ticket_id": ticket.ticket_id, "message": "A geração foi interrompida"},
                ensure_ascii=False,
            )
            yield f"event: error\ndata: {failure}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.post("/tickets/extraction")
def extract_order_data(ticket: TicketInput) -> OrderData:
    return extraction.extract(ticket, model)


def _run_topics(job_id: str, period: PeriodInput) -> None:
    jobs[job_id]["state"] = "running"

    def on_progress(done: int, total: int) -> None:
        jobs[job_id]["progress"] = f"{done}/{total}"

    try:
        jobs[job_id]["result"] = report.topics(period, model, on_progress)
        jobs[job_id]["state"] = "done"
    except Exception as error:
        detail = getattr(error, "detail", None) or str(error) or "A tarefa falhou"
        jobs[job_id]["detail"] = str(detail)
        jobs[job_id]["state"] = "failed"


@app.post("/reports/topics", status_code=202)
def topics_report(period: PeriodInput):
    if period.start > period.end:
        raise HTTPException(status_code=422, detail="A data inicial é posterior à data final")

    job_id = uuid4().hex[:12]
    jobs[job_id] = {"state": "pending", "progress": None, "result": None, "detail": None}
    Thread(target=_run_topics, args=(job_id, period), daemon=True).start()
    return JSONResponse(
        status_code=202,
        content={"state": "pending"},
        headers={
            "Location": f"/reports/topics/status/{job_id}",
            "Retry-After": "5",
        },
    )


@app.get("/reports/topics/status/{job_id}")
def topics_status(job_id: str):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    if job["state"] == "done":
        return Response(status_code=303, headers={"Location": f"/reports/topics/{job_id}"})
    body = {"state": job["state"]}
    if job["progress"]:
        body["progress"] = job["progress"]
    if job["state"] == "failed":
        body["detail"] = job["detail"]
    return body


@app.get("/reports/topics/{job_id}")
def topics_result(job_id: str):
    job = jobs.get(job_id)
    if job is None or job["state"] != "done":
        raise HTTPException(status_code=404, detail="Resultado não disponível")
    return job["result"]
