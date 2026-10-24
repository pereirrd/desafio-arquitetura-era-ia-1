import json
import os
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


def post(path, body):
    data = json.dumps(body).encode()
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_classifica_pedido_atrasado_e_urgente():
    status, body = post("/tickets/classification", TICKET)

    assert status == 200
    assert body == {
        "ticket_id": "TK-00042",
        "category": "delivery",
        "priority": "high",
    }


def test_classificacao_recusa_texto_vazio():
    status, body = post("/tickets/classification", {"ticket_id": "TK-00042", "text": ""})

    assert status == 422
    assert body == TEXTO_VAZIO


def test_sugere_resposta_para_pedido_atrasado():
    status, body = post("/tickets/reply-suggestion", TICKET)

    assert status == 200
    assert body == fixture("reply_suggestion.json")


def test_sugestao_recusa_texto_vazio():
    status, body = post("/tickets/reply-suggestion", {"ticket_id": "TK-00042", "text": ""})

    assert status == 422
    assert body == TEXTO_VAZIO


def test_relatorio_de_um_dia_de_agosto():
    status, body = post("/reports/topics", {"start": "2026-08-01", "end": "2026-08-01"})

    assert status == 200
    assert body == fixture("topics_2026_08_01.json")


def test_relatorio_recusa_periodo_invertido():
    status, body = post("/reports/topics", {"start": "2026-08-31", "end": "2026-08-01"})

    assert status == 422
    assert body == {"detail": "A data inicial é posterior à data final"}


def test_extrai_pedido_citado_no_ticket():
    status, body = post("/tickets/extraction", TICKET)

    assert status == 200
    assert body == {
        "ticket_id": "TK-00042",
        "order_number": "#481516",
        "product": None,
    }


def test_extracao_recusa_texto_vazio():
    status, body = post("/tickets/extraction", {"ticket_id": "TK-00042", "text": ""})

    assert status == 422
    assert body == TEXTO_VAZIO
