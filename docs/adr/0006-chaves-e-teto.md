# 0006. Aceitar dois providers e teto de US$ 50 na chave de trabalho

- Status: aceita
- Data: 2026-10-24
- Nível: corporativa

## Contexto

O helpdesk só pode gastar com os providers que a empresa aceita, e o gasto precisa de um teto que recuse a chamada antes do provider. O LiteLLM só aplica orçamento e limite de requisições em chave virtual persistida.

## Opções consideradas

1. Dois providers aceitos (o compatível com OpenAI e o Anthropic), três chaves virtuais criadas na subida, teto de US$ 50 por 30 dias na chave de trabalho.
2. Uma chave só, com o teto na aplicação.
3. Sem teto, só o limite de requisições.

## Decisão

A opção 1. Providers aceitos: os dois do provider simulado, e nenhum outro. A chave de trabalho `sk-helpdesk-app-0001` tem `max_budget` 50. A chave `sk-helpdesk-budget-0001` existe para demonstrar a recusa por orçamento: o teto é US$ 0,0000001, abaixo de uma classificação (cerca de US$ 0,00015). O gateway compara o gasto já registrado, não o custo estimado da chamada que está chegando, então a subida grava `spend` 1 nessa chave e a primeira chamada já é recusada. A chave `sk-helpdesk-rpm-0001` tem `rpm_limit` 0 e recusa na hora.

Nenhuma das três é chave de provider. As chaves dos providers ficam só no ambiente do gateway.

## Consequências

Estourar o teto não gera chamada em `/admin/calls`. A chave de demonstração de orçamento não serve para tráfego real: ela já nasce esgotada. Subir o teto de verdade é alterar `max_budget` da chave de trabalho no bootstrap e recriar as chaves.

## Evidência

`curl` em `localhost:4000/v1/chat/completions` com a chave de orçamento e com a de limite responde `429`. `GET http://localhost:8090/admin/calls` permanece com o mesmo tamanho de antes das duas recusas. O roteiro está no README.
