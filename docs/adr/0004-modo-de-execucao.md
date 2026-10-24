# 0004. Escolher o modo de execução de cada feature

- Status: aceita
- Data: 2026-10-24
- Nível: solução

## Contexto

As quatro features respondiam JSON síncrono. A borda corta em 30 s sem nenhum byte (`edge/nginx.conf`, `proxy_read_timeout 30s`). Medido na v1: F1 em 1,1 s; F2 em 16,0 s com o primeiro byte só no fim e 2.424 caracteres; um dia de F3 em 9,8 s; o mês em 504 aos 30,0 s e mais 30 chamadas `topics` depois disso, somando 5 min 31 s e US$ 0,85.

A pergunta de cada seção é a da árvore do requisito 6: alguém está esperando agora? cabe no orçamento de latência? é consumível aos poucos?

## F1 Classificar

Alguém está esperando: o cliente confirma a abertura na tela. A saída é um JSON curto de valores fixos, medido em 1,1 s, dentro dos 3 s. Não é consumível aos poucos: um pedaço de JSON não classifica o ticket.

Decisão: síncrono. Timeout de 5 s por destino no gateway. Com o primário em `timeout`, a resposta pelo `large` do outro provider chegou em 13,7 s.

## F2 Sugerir resposta

Alguém está esperando: o atendente lê e edita assim que o texto aparece. Não cabe entregar tudo de uma vez: 16 s com o primeiro byte no fim. É consumível aos poucos.

Decisão: `text/event-stream`. O primeiro trecho, medido pela borda com `curl -N`, chegou em 0,87 s, antes da metade dos 16,3 s totais. Um `midstream_error` no primário vira `event: error` dentro do stream, e `/admin/calls` mostra uma única chamada: o gateway não troca de modelo depois que um trecho saiu.

## F3 Relatório de temas

Ninguém está esperando olhando para a tela. O painel não oferece callback. O mês não cabe em 30 s nem em 60 s: são 34 lotes e cerca de 5 min 30 s. Não é consumível aos poucos: o painel precisa do agregado.

Decisão: Asynchronous Request-Reply no próprio processo. `POST` responde `202` com `Location` e `Retry-After` em menos de 1 s. O status fica em memória (`pending`, `running` com `progress`, `failed` com motivo) e, ao terminar, `303` aponta para o resultado. Sem fila e sem worker: sobreviver a um reinício no meio da tarefa está fora de escopo. O teto de 60 s vale só para a falha. Com os dois providers em `error_500`, a tarefa chegou a `failed` em 7,7 s, no primeiro lote.

## F4 Extrair dados do pedido

A automação espera o JSON inteiro. Um campo pela metade não dispara a troca. A saída cabe em cerca de 1 s. Não é consumível aos poucos.

Decisão: síncrono, com timeout de 5 s por destino. Com o primário em `timeout`, a extração respondeu em 13,6 s pelo `large` do outro provider.

## Opções consideradas

1. O modo acima, um por feature.
2. Tudo síncrono, aumentando o timeout da borda. A borda não pode ser editada, e o mês continuaria ocupando a conexão por minutos.
3. Fila e worker para o relatório. Resolve o reinício, que o requisito deixa fora de escopo, e adiciona um serviço sem ADR de requisito.

## Decisão

A opção 1.

## Consequências

A suíte da `main` acompanha o contrato novo. As tags `v1-coupled` e `v2-decoupled` continuam com o JSON síncrono. O estado do relatório some se o processo cair no meio.

## Evidência

`pytest tests/characterization` na `main` cobre o JSON da F1 e da F4, o texto remontado do stream da F2 e o relatório de um dia obtido pelo `303`. Os tempos citados estão nas seções acima e se repetem no README.
