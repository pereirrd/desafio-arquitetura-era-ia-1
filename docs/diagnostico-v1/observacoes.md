# Diagnóstico da v1

Medido em 2026-10-24, com o compose do repositório base no ar. `app/` foi restaurado ao original depois da troca temporária de modelo.

## 1. O relatório do mês morre na borda

```bash
curl -s -D - -o /tmp/mes.html -w 'ttfb:%{time_starttransfer} total:%{time_total}\n' \
  -X POST localhost:8000/reports/topics \
  -H 'Content-Type: application/json' \
  -d '{"start":"2026-08-01","end":"2026-08-31"}'
```

Resultado: **504** em **30,032 s**, **167 bytes**. O log da borda:

```text
upstream timed out (110: Operation timed out) while reading response header from upstream
POST /reports/topics HTTP/1.1 504 167
```

Causa: `report.py` percorre os 5.000 tickets em lotes de 150, um depois do outro, e só devolve a resposta no fim. A borda, em `edge/nginx.conf`, corta com `proxy_read_timeout 30s` se nenhum byte chega.

O mês gerou **34** chamadas `topics`. Cada lote de 150 levou cerca de **9,8 s**. Trinta segundos não cobrem o mês.

## 2. A borda desiste e a aplicação continua pagando

O mesmo pedido do item 1. A borda respondeu às 15:58:09. A primeira chamada tinha começado às 15:57:39.969. Nesse instante já havia **4** chamadas recebidas (3 concluídas). As outras **30** começaram depois do 504.

A última começou às 16:03:02.691 e terminou cerca de **8,7 s** depois. O trabalho seguiu por **5 min 31 s** no total (soma das durações: **331,3 s**).

As 34 chamadas foram `anthropic` / `claude-fake-large` / `topics`, todas `200`, `stream=false`.

| | Tokens |
|---|---|
| entrada | 222.114 |
| saída | 12.162 |

Preço publicado do `claude-fake-large`: US$ 3,00 / 1M de entrada e US$ 15,00 / 1M de saída. Custo calculado: **US$ 0,85**, pago depois de o cliente já ter recebido 504.

Causa: `report.py` não acompanha o cancelamento da conexão.

## 3. A sugestão deixa o atendente no escuro

```bash
curl -s -D - -o /tmp/f2.json -w 'ttfb:%{time_starttransfer} total:%{time_total}\n' \
  -X POST localhost:8000/tickets/reply-suggestion \
  -H 'Content-Type: application/json' \
  -d '{"ticket_id":"TK-00042","text":"Meu pedido #481516 não chegou e já passou do prazo, urgente"}'
```

Resultado: **200** `application/json`, **2.606 bytes**, sugestão de **2.424 caracteres**. Tempo até o primeiro byte **15,957 s**, igual ao tempo total.

`/admin/calls`: `anthropic` / `claude-fake-large` / `suggest`, `stream=false`, 606 tokens de saída, **15.952 ms**.

Causa: `suggestion.py` espera `call_anthropic` devolver o texto inteiro. Não há streaming.

## 4. Metade do helpdesk para com um provider

```bash
curl -s -X POST localhost:8090/admin/failures \
  -H 'Content-Type: application/json' \
  -d '{"provider":"openai","mode":"error_500"}'
```

A F3 abaixo usa só `2026-08-01`, para a falha vista ser a do provider e não o 504 do mês.

| Feature | OpenAI em `error_500` | Anthropic em `error_500` |
|---|---|---|
| F1 classificar | 500 em 1,343 s, corpo `Internal Server Error` | 200 em 1,081 s, `delivery` / `high` |
| F2 sugerir | 200 em 15,966 s, 2.424 caracteres | 500 em 1,211 s |
| F3 relatório de um dia | 200 em 9,827 s, 137 tickets | 500 em 1,407 s |
| F4 extrair | 500 em 1,200 s | 200 em 1,090 s, `#481516` |

Cada feature que caiu deixou **3** chamadas `500` no provider derrubado. A outra metade fez **1** chamada `200` no provider que seguia. `max_retries` padrão dos SDKs é 2, então a tentativa inicial mais dois retries.

Causa: `config.py` fixa OpenAI para F1 e F4 e Anthropic para F2 e F3. `llm.py` chama o SDK daquele provider.

## 5. Trocar o modelo exige código e rebuild

`CLASSIFICATION_MODEL` foi alterado para `gpt-fake-mini` e o serviço `app` foi reconstruído (`docker compose up -d --build app --wait`). A imagem copia `helpdesk/` no build; reiniciar o container sem rebuild não lê o arquivo do host.

A mesma F1 respondeu o mesmo JSON (`delivery` / `high`). Em `/admin/calls` o modelo foi `gpt-fake-mini`, **374 ms**.

A linha foi desfeita e o `app` reconstruído de novo. A chamada seguinte usou `gpt-fake-large`, **1.076 ms**. `git diff` em `app/` ficou vazio.

## Padrões dos SDKs e os 30 s da borda

Medido dentro do container `app`. `llm.py` não define timeout nem retry.

| SDK | Versão | `max_retries` | Timeout de leitura |
|---|---|---|---|
| `openai` | 3.19.0 | 2 | 600 s |
| `anthropic` | 1.8.0 | 2 | 600 s |

A borda desiste em 30 s. O SDK espera até 600 s por tentativa e ainda repete duas vezes. No `error_500`, as três tentativas apareceram em `/admin/calls`.
