# 0001. Usar Postgres só para chave, orçamento e limite

- Status: aceita
- Data: 2026-10-24
- Nível: solução

## Contexto

O requisito 5 exige recusar uma chamada antes de ela chegar ao provider, por orçamento e por limite de requisições, e a chave da aplicação tem de existir na subida, sem passo manual. O LiteLLM Proxy só persiste chave virtual, gasto e limite quando tem um banco. A fila e o worker não entram: o relatório assíncrono vive no processo da aplicação, e sobreviver a um reinício está fora de escopo.

## Opções consideradas

1. Postgres, o banco que o LiteLLM já migra na subida.
2. SQLite no volume do gateway.
3. Não ter banco e controlar o teto na aplicação.

## Decisão

Postgres 16 como serviço `postgres`. O gateway recebe `DATABASE_URL` e o entrypoint cria as três chaves antes de o healthcheck passar. A aplicação só enxerga a chave de trabalho.

## Consequências

Sobe mais um serviço, justificado pelo requisito de governança. O volume guarda as chaves entre reinícios. Não há fila nem worker para explicar.

## Evidência

`docker compose up -d --build --wait` deixa o gateway saudável sem comando extra. Uma chamada com a chave de orçamento ou de limite não aumenta `GET http://localhost:8090/admin/calls`.
