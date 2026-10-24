import json
import os
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:4000"
MASTER = os.environ["LITELLM_MASTER_KEY"]
MODELS = ["helpdesk-classify", "helpdesk-suggest", "helpdesk-topics", "helpdesk-extract"]


def wait_until_ready() -> None:
    last_error = None
    for _ in range(90):
        try:
            with urllib.request.urlopen(f"{BASE}/health/liveliness", timeout=2) as response:
                response.read()
            return
        except Exception as error:
            last_error = error
            time.sleep(2)
    raise SystemExit(f"gateway não ficou pronto: {last_error}")


def generate(payload: dict) -> None:
    request = urllib.request.Request(
        f"{BASE}/key/generate",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {MASTER}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read()
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        if error.code in {400, 409} and "already" in body.lower():
            return
        raise SystemExit(f"falha ao criar chave {payload.get('key_alias')}: {error.code} {body}") from error


def main() -> None:
    wait_until_ready()
    generate({
        "key": os.environ["GATEWAY_APP_KEY"],
        "key_alias": "helpdesk-app",
        "models": MODELS,
        "max_budget": 50,
        "budget_duration": "30d",
    })
    generate({
        "key": os.environ["GATEWAY_BUDGET_KEY"],
        "key_alias": "helpdesk-budget",
        "models": MODELS,
        "max_budget": 0.0000001,
        "budget_duration": "30d",
    })
    generate({
        "key": os.environ["GATEWAY_RPM_KEY"],
        "key_alias": "helpdesk-rpm",
        "models": MODELS,
        "rpm_limit": 0,
    })


if __name__ == "__main__":
    main()
