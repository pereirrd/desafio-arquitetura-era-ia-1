import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = os.environ.get("HELPDESK_URL", "http://127.0.0.1:8000")
FIXTURES = Path(__file__).parent / "fixtures"
TICKET = {
    "ticket_id": "TK-00042",
    "text": "Meu pedido #481516 não chegou e já passou do prazo, urgente",
}
TEXTO_VAZIO = {
    "detail": [
        {
            "type": "string_too_short",
            "loc": ["body", "text"],
            "msg": "String should have at least 1 character",
            "input": "",
            "ctx": {"min_length": 1},
        }
    ]
}


class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_SemRedirecionar)


def post(path, body):
    data = json.dumps(body).encode()
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with _opener.open(request, timeout=40) as response:
            return response.status, response.headers, json.loads(response.read().decode() or "null")
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        body_json = json.loads(raw) if raw else None
        return error.code, error.headers, body_json


def get(path):
    request = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    try:
        with _opener.open(request, timeout=40) as response:
            raw = response.read().decode()
            parsed = json.loads(raw) if raw else None
            return response.status, response.headers, parsed
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        parsed = json.loads(raw) if raw else None
        return error.code, error.headers, parsed


def eventos(raw):
    chunks = []
    end = None
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data = None
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())
        if event == "end":
            end = data
        elif data and "chunk" in data:
            chunks.append(data["chunk"])
    return "".join(chunks), end


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_classifica_pedido_atrasado_e_urgente():
    status, _headers, body = post("/tickets/classification", TICKET)

    assert status == 200
    assert body == {
        "ticket_id": "TK-00042",
        "category": "delivery",
        "priority": "high",
    }


def test_classificacao_recusa_texto_vazio():
    status, _headers, body = post("/tickets/classification", {"ticket_id": "TK-00042", "text": ""})

    assert status == 422
    assert body == TEXTO_VAZIO


def test_sugere_resposta_para_pedido_atrasado():
    data = json.dumps(TICKET).encode()
    request = urllib.request.Request(
        f"{BASE_URL}/tickets/reply-suggestion",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        assert response.status == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        suggestion, end = eventos(response.read().decode())

    expected = fixture("reply_suggestion.json")
    assert suggestion == expected["suggestion"]
    assert end == {"ticket_id": expected["ticket_id"]}


def test_sugestao_recusa_texto_vazio():
    status, _headers, body = post("/tickets/reply-suggestion", {"ticket_id": "TK-00042", "text": ""})

    assert status == 422
    assert body == TEXTO_VAZIO


def test_relatorio_de_um_dia_de_agosto():
    status, headers, body = post("/reports/topics", {"start": "2026-08-01", "end": "2026-08-01"})

    assert status == 202
    assert body == {"state": "pending"}
    assert headers["Retry-After"] == "5"
    location = headers["Location"]
    assert location.startswith("/reports/topics/status/")

    deadline = time.monotonic() + 40
    result_path = None
    while time.monotonic() < deadline:
        state, state_headers, state_body = get(location)
        if state == 303:
            result_path = state_headers["Location"]
            break
        assert state == 200
        assert state_body["state"] in {"pending", "running"}
        time.sleep(0.5)

    assert result_path is not None
    status, _headers, body = get(result_path)
    assert status == 200
    assert body == fixture("topics_2026_08_01.json")


def test_relatorio_recusa_periodo_invertido():
    status, _headers, body = post("/reports/topics", {"start": "2026-08-31", "end": "2026-08-01"})

    assert status == 422
    assert body == {"detail": "A data inicial é posterior à data final"}


def test_extrai_pedido_citado_no_ticket():
    status, _headers, body = post("/tickets/extraction", TICKET)

    assert status == 200
    assert body == {
        "ticket_id": "TK-00042",
        "order_number": "#481516",
        "product": None,
    }


def test_extracao_recusa_texto_vazio():
    status, _headers, body = post("/tickets/extraction", {"ticket_id": "TK-00042", "text": ""})

    assert status == 422
    assert body == TEXTO_VAZIO
