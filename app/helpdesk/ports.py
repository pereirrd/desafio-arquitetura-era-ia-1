from collections.abc import Iterator
from typing import Protocol


class TicketModel(Protocol):
    def complete(self, capability: str, task: str, content: str) -> str:
        """Devolve o texto completo do modelo para uma tarefa do helpdesk."""

    def stream(self, capability: str, task: str, content: str) -> Iterator[str]:
        """Entrega o texto do modelo em trechos, na ordem em que ele é gerado."""
