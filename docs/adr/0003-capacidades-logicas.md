# 0003. Nomear capacidades e apontá-las para os modelos large

- Status: aceita
- Data: 2026-10-24
- Nível: solução

## Contexto

A v1 usava `gpt-fake-large` em F1 e F4 e `claude-fake-large` em F2 e F3. Os dois `large` produzem a mesma saída. Os `mini` não: a sugestão encolhe e a extração pode pegar o número errado. A tag `v2-decoupled` precisava manter o corpo que a suíte de caracterização fixou.

## Opções consideradas

1. Quatro nomes lógicos, cada um apontando para o `large` do provider que a v1 já usava.
2. Um único nome lógico para as quatro features.
3. Apontar alguma feature para `mini` já na v2, para baratear.

## Decisão

A opção 1. A aplicação pede `helpdesk-classify`, `helpdesk-suggest`, `helpdesk-topics` e `helpdesk-extract`. Na configuração, classificação e extração vão para `openai/gpt-fake-large`; sugestão e temas vão para `anthropic/claude-fake-large`. Os destinos de fallback têm nomes próprios (`-backup` e `-mini`) e não aparecem na aplicação.

Os preços por token estão em `litellm_params`, senão o LiteLLM conta custo zero e o orçamento não estoura. São os preços do README do provider, divididos por um milhão.

## Consequências

Trocar o modelo físico é editar `gateway/config.yaml` e reiniciar só o `gateway`. A suíte continua válida porque o `large` de cada lado responde igual ao da v1.

## Evidência

Depois de `pytest tests/characterization`, `GET http://localhost:8090/admin/calls` mostra `gpt-fake-large` nas tarefas `classify` e `extract`, e `claude-fake-large` nas tarefas `suggest` e `topics`.
