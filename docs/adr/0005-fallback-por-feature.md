# 0005. Cair para o outro large e, só em alguns casos, para o mini

- Status: aceita
- Data: 2026-10-24
- Nível: solução

## Contexto

Os dois `large` são equivalentes. Os `mini` são mais rápidos e piores. Medido direto no provider, com o texto da nota fiscal `A nota fiscal 392817 refere-se ao pedido #481516 do fone de ouvido bluetooth, que veio com defeito`:

| Modelo | Extração |
|---|---|
| `large` | `order_number` `#481516`, `product` `fone de ouvido bluetooth` |
| `mini` | `order_number` `#392817`, `product` `null` |

Na classificação, o `mini` devolve o mesmo JSON (`delivery` / `high`). Em temas, ignora o tamanho e devolve a mesma estrutura. Na sugestão, o alvo do `mini` é cerca de 1.000 caracteres; a resposta medida ficou utilizável para o atendente editar.

O gateway faz no máximo 2 tentativas por destino (`num_retries: 1` é a tentativa extra). O SDK da aplicação fica com `max_retries=0`, para as tentativas não se multiplicarem. Timeout de 5 s em classificação e extração, 25 s na sugestão `large` (a geração saudável leva cerca de 16 s) e 20 s no lote de temas.

## F1 Classificar

Fallback técnico: `claude-fake-large`. Sem nenhum `large`, usa `gpt-fake-mini`. A resposta é a mesma e o cliente está esperando. Uma resposta pior, neste caso, não é pior.

Evidência: com o provider `openai` em `error_500`, `/admin/calls` mostrou 2 chamadas `500` em `gpt-fake-large` e 1 `200` em `claude-fake-large`. Com os dois `large` em `error_500`, a chamada seguinte foi `gpt-fake-mini` e o corpo continuou `delivery` / `high`.

## F2 Sugerir resposta

Fallback técnico: `gpt-fake-large`. Sem nenhum `large`, usa `claude-fake-mini`. O texto fica mais curto e o atendente ainda tem o que editar. Isso é melhor do que a tela vazia.

Se um trecho já foi enviado, a falha não troca de modelo. O `midstream_error` do primário produziu `event: error` e uma única chamada em `/admin/calls`.

Evidência: com os dois `large` em `error_500`, a sugestão respondeu `200` via `claude-fake-mini`.

## F3 Relatório de temas

Fallback técnico: `gpt-fake-large`. Sem nenhum `large`, usa `claude-fake-mini`. O `mini` mantém os temas, então o painel ainda recebe o agregado. Se o `mini` também cai, a tarefa vai a `failed` no primeiro lote, com motivo, e não percorre os 34.

Evidência: com os dois providers inteiros em `error_500`, `/admin/calls` mostrou 2 tentativas em cada `large` e 2 no `mini`, todas `500`, e o status ficou `failed` em 7,7 s.

## F4 Extrair dados do pedido

Fallback técnico: `claude-fake-large`. Sem nenhum `large`, a aplicação responde `502` com `{"detail":"A capacidade helpdesk-extract não respondeu"}`. Não há `mini`. Um número de pedido trocado dispara a troca errada, e o `product` nulo some com o item.

Evidência: com os dois `large` em `error_500`, `/admin/calls` mostrou 2 tentativas em `gpt-fake-large` e 2 em `claude-fake-large`, nenhuma em `mini`, e a borda respondeu `502`.

## Opções consideradas

1. A política acima, por feature.
2. `mini` em todas, inclusive na extração.
3. Falhar em todas quando o `large` acaba, inclusive onde o `mini` não muda o resultado.

## Decisão

A opção 1. O mecanismo mora no gateway (`litellm_settings.fallbacks`). A aplicação só traduz a falha final em erro explícito.

## Consequências

Classificação e extração aguentam o primário travado por 300 s e respondem em menos de 15 s. A sugestão saudável continua podendo levar cerca de 16 s, porque o timeout dela cobre a geração. O `mini` da extração fica de fora de propósito.

## Evidência

Os três cenários, com `POST /admin/reset` entre eles, estão descritos nas seções. O número de tentativas por destino no README é 2.
