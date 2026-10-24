import os

from openai import OpenAI

from .ports import TicketModel

MAX_OUTPUT_TOKENS = 2000


class ModelUnavailable(RuntimeError):
    """O gateway esgotou as tentativas e os destinos desta capacidade."""


class GatewayClient:
    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=os.environ["GATEWAY_API_KEY"],
            base_url=os.environ["GATEWAY_BASE_URL"],
            max_retries=0,
            timeout=float(os.environ.get("GATEWAY_TIMEOUT", "40")),
        )

    def complete(self, capability: str, task: str, content: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=capability,
                max_tokens=MAX_OUTPUT_TOKENS,
                messages=[{"role": "user", "content": f"TASK: {task}\n{content}"}],
            )
        except Exception as error:
            raise ModelUnavailable(f"A capacidade {capability} não respondeu") from error
        content_text = response.choices[0].message.content
        if content_text is None:
            raise ModelUnavailable(f"A capacidade {capability} não devolveu conteúdo")
        return content_text

    def stream(self, capability: str, task: str, content: str):
        try:
            response = self._client.chat.completions.create(
                model=capability,
                max_tokens=MAX_OUTPUT_TOKENS,
                stream=True,
                messages=[{"role": "user", "content": f"TASK: {task}\n{content}"}],
            )
            for chunk in response:
                if not chunk.choices:
                    continue
                piece = chunk.choices[0].delta.content
                if piece:
                    yield piece
        except Exception as error:
            raise ModelUnavailable(f"A capacidade {capability} não respondeu") from error


def build_client() -> TicketModel:
    return GatewayClient()
