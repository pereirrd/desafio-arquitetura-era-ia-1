import os

from openai import OpenAI

from .ports import TicketModel

MAX_OUTPUT_TOKENS = 2000


class GatewayClient:
    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=os.environ["GATEWAY_API_KEY"],
            base_url=os.environ["GATEWAY_BASE_URL"],
            max_retries=0,
            timeout=float(os.environ.get("GATEWAY_TIMEOUT", "40")),
        )

    def complete(self, capability: str, task: str, content: str) -> str:
        response = self._client.chat.completions.create(
            model=capability,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": f"TASK: {task}\n{content}"}],
        )
        content_text = response.choices[0].message.content
        if content_text is None:
            raise RuntimeError("O gateway não devolveu conteúdo")
        return content_text


def build_client() -> TicketModel:
    return GatewayClient()
