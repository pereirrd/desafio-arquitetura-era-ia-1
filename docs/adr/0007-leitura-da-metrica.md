# 0007. Ler a métrica com schemas como única exceção

- Status: aceita
- Data: 2026-10-24
- Nível: software

## Contexto

A régua é a do requisito 3. Na v1, `config` (I 0,00, D 1,00) e `llm` (I 0,20, D 0,80) estavam na zona de dor, junto com `schemas`. O piloto da classificação tirou essa feature de `llm.py`, e o módulo continuou na zona: Ca caiu de 4 para 3 e I ficou 0,25. A revisão do plano está em `docs/refactoring-plan.md`.

A zona de dor é A < 0,5 e I < 0,5 e D ≥ 0,5 ao mesmo tempo. I = 0,50 não entra.

## Opções consideradas

1. Apagar `llm.py`, `config.py` e `tickets.py`. As features dependem do `Protocol` em `ports.py`. O cliente concreto importa esse módulo e não herda o `Protocol`. Só `main.py` importa o cliente. A leitura dos tickets mora em `report.py`. `schemas.py` fica como exceção.
2. Manter `schemas.py` fora da exceção e espalhar os tipos para "melhorar" o número.
3. Criar imports sem uso para tirar módulos da zona.

## Decisão

A opção 1. `schemas.py` é a única exceção. São tipos de valor do pydantic, estáveis por natureza: não têm política, não chamam modelo e não decidem fluxo. Mudá-los é mudar o contrato, não a estrutura. O componente que chama o gateway (`gateway.py`, I 0,50, D 0,50) e as quatro features (I 0,67) não são exceção.

O cliente importa `ports` porque precisa do contrato que implementa, e só a composição em `main.py` depende dele. Isso é a inversão: a feature não conhece o SDK. O I 0,50 que resulta está fora da zona pela régua, sem import artificial.

## Consequências

`metrics/results/main.csv` e `v2-decoupled.csv` têm um único componente na zona: `schemas`. `ports` fica em A 1,00 e D 0,00. Quem for ler o gráfico não trata o ponto de `schemas` como dívida.

## Evidência

`python3 metrics/measure.py app/helpdesk main` imprime `schemas` com I 0,00, A 0,00 e D 1,00, e `gateway` com I 0,50, A 0,00 e D 0,50. Nenhum outro componente cai na zona.
