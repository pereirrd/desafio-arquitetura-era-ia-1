# Helpdesk

O helpdesk classifica ticket, sugere resposta, extrai o pedido e agrega temas. A aplicação pede uma capacidade lógica ao gateway. O gateway (LiteLLM Proxy) escolhe o modelo físico, aplica timeout, retry, fallback, orçamento e limite. Quando um provider cai, a mesma capacidade segue no `large` do outro. Classificação, sugestão e temas ainda aceitam o `mini` se os dois `large` caírem. A extração não: responde erro, porque um número trocado dispara a troca errada.

O único módulo que chama o SDK é `app/helpdesk/gateway.py`. Só `main.py` o importa.

## Diagnóstico da v1

Medido em 2026-10-24, com o compose do repositório base. O detalhe e os arquivos brutos estão em `docs/diagnostico-v1/`.

### O relatório do mês não chega

```bash
curl -s -D - -o /tmp/mes.html -w 'ttfb:%{time_starttransfer} total:%{time_total}\n' \
  -X POST localhost:8000/reports/topics \
  -H 'Content-Type: application/json' \
  -d '{"start":"2026-08-01","end":"2026-08-31"}'
```

Resultado: **504** em **30,032 s**, **167 bytes**. O log da borda: `upstream timed out (110: Operation timed out) while reading response header from upstream`.

A mesma requisição continuou depois do 504. Das **34** chamadas `topics`, **30** começaram depois da resposta. O trabalho levou **5 min 31 s** (soma das durações **331,3 s**), **222.114** tokens de entrada e **12.162** de saída. A US$ 3,00 e US$ 15,00 por milhão, **US$ 0,85** pagos com o cliente já em 504.

Causa: `app/helpdesk/report.py` percorria os 5.000 tickets em lotes de 150 e só respondia no fim. `edge/nginx.conf` corta com `proxy_read_timeout 30s`. O método não observava o cancelamento da conexão.

### A sugestão deixa o atendente sem ver nada

```bash
curl -s -D - -o /tmp/f2.json -w 'ttfb:%{time_starttransfer} total:%{time_total}\n' \
  -X POST localhost:8000/tickets/reply-suggestion \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

Resultado: **200** `application/json`, **2.424 caracteres**. Tempo até o primeiro byte **15,957 s**, igual ao tempo total. Em `/admin/calls`: `claude-fake-large`, `suggest`, `stream=false`, **15.952 ms**.

Causa: `app/helpdesk/suggestion.py` esperava o texto inteiro de `call_anthropic` em `llm.py`.

### Com um provider fora, metade do helpdesk para

```bash
curl -s -X POST localhost:8090/admin/failures \
  -H 'Content-Type: application/json' \
  -d '{"provider":"openai","mode":"error_500"}'
```

| Feature | OpenAI em `error_500` | Anthropic em `error_500` |
|---|---|---|
| F1 classificar | 500 em 1,343 s | 200 em 1,081 s |
| F2 sugerir | 200 em 15,966 s | 500 em 1,211 s |
| F3 um dia | 200 em 9,827 s, 137 tickets | 500 em 1,407 s |
| F4 extrair | 500 em 1,200 s | 200 em 1,090 s, `#481516` |

Cada feature que caiu deixou **3** chamadas `500`. O SDK estava no padrão: `max_retries=2` e timeout de leitura de **600 s**, contra **30 s** da borda.

Causa: `config.py` fixava OpenAI para F1 e F4 e Anthropic para F2 e F3. `llm.py` não definia timeout nem retry.

### Trocar o modelo exige código e rebuild

`CLASSIFICATION_MODEL` foi para `gpt-fake-mini` e o serviço `app` foi reconstruído. A mesma F1 devolveu o mesmo JSON, e `/admin/calls` mostrou `gpt-fake-mini` em **374 ms**. A imagem copia `helpdesk/` no build: reiniciar sem rebuild não lê o arquivo do host.

Causa: o nome físico vivia em `app/helpdesk/config.py`. A linha foi desfeita e o `app` reconstruído de novo antes de seguir.

## Como rodar

```bash
cp .env.example .env
docker compose up -d --build --wait
curl -s localhost:8000/health
```

O health responde `{"status":"ok"}` sem passo manual. O gateway só fica saudável depois de criar as três chaves.

Testes de caracterização, com a stack no ar:

```bash
python3 -m pytest tests/characterization -q
```

Métrica, a partir da raiz do repositório:

```bash
python3 metrics/measure.py app/helpdesk main
```

O primeiro argumento é a pasta `app/helpdesk`. O segundo é o nome do CSV e do SVG em `metrics/results/`.

## Métrica

A zona de dor é A < 0,5, I < 0,5 e D ≥ 0,5 ao mesmo tempo. I = 0,50 não entra.

| Versão | O que saiu da zona | Por quê |
|---|---|---|
| `v1-coupled` | `config` e `llm` estavam nela, com `schemas` | Todo mundo importava a configuração, e quatro features importavam o cliente concreto |
| `v2-decoupled` | `config` e `llm` deixaram de existir | As features passam a depender do `Protocol`. O cliente do gateway só é importado por `main.py` e fica em I 0,50 |
| `main` | o mesmo desenho da v2 | Streaming e o relatório assíncrono não criaram componente novo |

O piloto, só na classificação, baixou o Ca de `llm` de 4 para 3. I ficou 0,25 e o módulo continuou na zona. A revisão está em `docs/refactoring-plan.md`: embrulhar o cliente não basta; o módulo foi removido na escala.

A única exceção declarada é `schemas`. Justificativa em `docs/adr/0007-leitura-da-metrica.md`. `gateway.py` e as features não são exceção.

## Tabela de capacidades

No máximo **2 tentativas por destino** (a chamada e mais uma). O SDK da aplicação não repete.

| Capacidade | Feature | Primário | Fallback técnico | Modelo fraco | Tentativas por destino |
|---|---|---|---|---|---|
| `helpdesk-classify` | F1 | `gpt-fake-large` | `claude-fake-large` | `gpt-fake-mini` | 2 |
| `helpdesk-suggest` | F2 | `claude-fake-large` | `gpt-fake-large` | `claude-fake-mini` | 2 |
| `helpdesk-topics` | F3 | `claude-fake-large` | `gpt-fake-large` | `claude-fake-mini` | 2 |
| `helpdesk-extract` | F4 | `gpt-fake-large` | `claude-fake-large` | não usa | 2 |

Timeout por destino: 5 s em F1 e F4, 25 s no `large` da F2, 20 s no `large` da F3, 10 s nos `mini` de F2 e F3. Preços por token estão em `gateway/config.yaml`.

## Tabela de fallback

Quando nenhum `large` responde:

| Feature | O que o cliente recebe |
|---|---|
| F1 | `200` com a classificação do `mini`. No ticket de exemplo, `delivery` / `high` |
| F2 | `200` `text/event-stream` com o texto mais curto do `mini` |
| F3 | o relatório do `mini`. Se o `mini` também cair, `200` no status com `{"state":"failed","detail":...}`, no primeiro lote, em até 60 s |
| F4 | `502` `{"detail":"A capacidade helpdesk-extract não respondeu"}` |

Um trecho de F2 que já saiu não troca de modelo. A falha no meio chega como `event: error` dentro do stream.

## Fluxos

### F1 Classificar, síncrono

```bash
curl -s -D - -X POST localhost:8000/tickets/classification \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

`200` e `{"ticket_id":"TK-00042","category":"delivery","priority":"high"}`. Cabe em 3 s.

### F2 Sugerir, streaming

```bash
curl -N -s -D - -X POST localhost:8000/tickets/reply-suggestion \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

`Content-Type: text/event-stream`. Trechos `data: {"chunk":"..."}`. Fim com `event: end` e `data: {"ticket_id":"TK-00042"}`. A aplicação envia `X-Accel-Buffering: no`; a borda consome esse header para não acumular a resposta, então ele não aparece no `curl` da porta 8000. O primeiro trecho chega em até 1,5 s e antes da metade do tempo total.

Erro no meio:

```text
event: error
data: {"ticket_id":"TK-00042","message":"A geração foi interrompida"}
```

### F3 Temas, assíncrono

```bash
curl -s -D - -X POST localhost:8000/reports/topics \
  -H 'Content-Type: application/json' \
  -d '{"start":"2026-08-01","end":"2026-08-31"}'
```

`202`, `Location: /reports/topics/status/<id>`, `Retry-After: 5`. O mês é aceito em até 1 s.

```bash
curl -s -D - localhost:8000/reports/topics/status/<id>
```

Enquanto trabalha: `200` `{"state":"running","progress":"1800/5000"}`. Falha: `200` `{"state":"failed","detail":"..."}`. Sucesso: `303` e `Location: /reports/topics/<id>`.

```bash
curl -s localhost:8000/reports/topics/<id>
```

`200` com `total_tickets` **5000** no mês. As chamadas `topics` que produziram o relatório estão em `GET http://localhost:8090/admin/calls`.

Período invertido continua síncrono: `422` `{"detail":"A data inicial é posterior à data final"}`.

### F4 Extrair, síncrono

```bash
curl -s -D - -X POST localhost:8000/tickets/extraction \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

`200` e `{"ticket_id":"TK-00042","order_number":"#481516","product":null}`.

## Troca de modelo

Edite só o campo `model` da capacidade em `gateway/config.yaml`. Exemplo, classificação para o mini:

```yaml
model: openai/gpt-fake-mini
```

```bash
docker compose restart gateway
```

Não reconstrua e não reinicie o `app`. A próxima classificação aparece em `/admin/calls` com `gpt-fake-mini`.

## Roteiro de governança

Com a stack no ar. As recusas acontecem no gateway e não aumentam `/admin/calls`.

```bash
curl -s -X POST localhost:8090/admin/reset
curl -s localhost:8090/admin/calls
```

A segunda resposta é `[]`.

Orçamento estourado (`max_budget` US$ 0,0000001, gasto inicial US$ 1):

```bash
curl -s -D - -X POST localhost:4000/v1/chat/completions \
  -H 'Authorization: Bearer sk-helpdesk-budget-0001' \
  -H 'Content-Type: application/json' \
  -d '{"model":"helpdesk-classify","max_tokens":20,"messages":[{"role":"user","content":"TASK: classify\nMeu pedido #481516 não chegou"}]}'
```

Resposta `429` com `budget_exceeded`.

Limite de requisições (`rpm_limit` 0):

```bash
curl -s -D - -X POST localhost:4000/v1/chat/completions \
  -H 'Authorization: Bearer sk-helpdesk-rpm-0001' \
  -H 'Content-Type: application/json' \
  -d '{"model":"helpdesk-classify","max_tokens":20,"messages":[{"role":"user","content":"TASK: classify\nMeu pedido #481516 não chegou"}]}'
```

Resposta `429` com limite de requests. `curl -s localhost:8090/admin/calls` continua `[]`.

A chave de trabalho, usada pelo `app`, é `sk-helpdesk-app-0001`, com teto de US$ 50 a cada 30 dias.

## Mapa de decisões

| ADR | Nível | Resumo |
|---|---|---|
| [0001](docs/adr/0001-postgres-para-chaves.md) | solução | Postgres só para chave virtual, orçamento e limite |
| [0002](docs/adr/0002-gateway-na-frente.md) | solução | LiteLLM na frente; a aplicação não vê provider |
| [0003](docs/adr/0003-capacidades-logicas.md) | solução | Quatro capacidades, todas em `large` no caminho feliz |
| [0004](docs/adr/0004-modo-de-execucao.md) | solução | F1 e F4 síncronas, F2 em stream, F3 assíncrona no processo |
| [0005](docs/adr/0005-fallback-por-feature.md) | solução | Outro `large` sempre; `mini` em F1, F2 e F3; F4 falha |
| [0006](docs/adr/0006-chaves-e-teto.md) | corporativa | Dois providers aceitos e teto de US$ 50 na chave de trabalho |
| [0007](docs/adr/0007-leitura-da-metrica.md) | software | `schemas` é a única exceção da zona de dor |
