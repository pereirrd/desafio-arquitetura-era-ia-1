from typing import Protocol


class TicketModel(Protocol):
    def complete(self, task: str, content: str) -> str:
        """Devolve o texto completo do modelo para uma tarefa do helpdesk."""
