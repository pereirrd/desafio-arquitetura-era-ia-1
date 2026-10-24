# 0002. Colocar o LiteLLM entre a aplicação e os providers

- Status: aceita
- Data: 2026-10-24
- Nível: solução

## Contexto

Na v1, `app/helpdesk/llm.py` chamava o SDK de cada provider e `config.py` guardava o nome físico do modelo e a chave. Derrubar um provider derrubava as features daquele lado, e trocar o modelo exigia rebuild da imagem. O requisito 5 pede capacidades lógicas, chave virtual, orçamento, limite e fallback num lugar só.

## Opções consideradas

1. LiteLLM Proxy (`ghcr.io/berriai/litellm:v1.102.1`) como serviço `gateway`, falando a API compatível com OpenAI.
2. Continuar com os dois SDKs na aplicação e só esconder os nomes atrás de variáveis.
3. Um proxy escrito à mão na aplicação.

## Decisão

A opção 1. A aplicação fala só com `http://gateway:4000/v1`, com `max_retries=0` no SDK. Nomes físicos e chaves dos providers ficam em `gateway/config.yaml`. O único módulo que importa o SDK é `app/helpdesk/gateway.py`, e só `main.py` o importa.

## Consequências

Os dois providers passam a ter o mesmo formato de chamada. Retry e fallback deixam de se multiplicar com o padrão do SDK (que era `max_retries=2` e timeout de leitura de 600 s). O compose ganha o gateway e o Postgres que ele exige para persistir chave.

## Evidência

`grep -rE "gpt-fake|claude-fake|FAKE_OPENAI_KEY|FAKE_ANTHROPIC_KEY" app/` não imprime nada. `docker compose exec app env` mostra `GATEWAY_API_KEY` e não mostra as chaves dos providers. Uma classificação aparece em `GET http://localhost:8090/admin/calls` como chamada ao modelo físico mapeado no gateway, não como chamada direta da aplicação.
