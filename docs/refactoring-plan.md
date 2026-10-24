# Plano de refatoração

O ponto de partida é a tag `v1-coupled`, medida em `metrics/results/v1-coupled.csv`. Na zona de dor estão `config` (Ca 6, I 0,00, D 1,00), `llm` (Ca 4, I 0,20, D 0,80) e `schemas` (Ca 5, I 0,00, D 1,00). `schemas` é tipo de valor e será a única exceção declarada no ADR da métrica. `config` e `llm` não são exceção.

## Componentes-alvo

- `llm.py`: some. Um único cliente do gateway passa a ser o único módulo que chama o SDK.
- `config.py`: some. Nome físico de modelo e chave de provider saem da aplicação.
- `tickets.py`: a leitura do arquivo passa para o relatório, para o módulo não virar folha concreta.
- `classification.py`, `suggestion.py`, `extraction.py`, `report.py`: passam a depender de um `Protocol`.
- `main.py`: único ponto que importa o cliente concreto e monta as features.
- `ports.py`: só o contrato. Nasce no piloto.

## Estratégia

- Subir A em `ports.py`: uma classe `Protocol`, sem dependência de outro componente.
- Reduzir Ca de `llm` e `config` até os módulos deixarem de existir. A feature não escolhe provider.
- Inverter a dependência: a feature pede uma capacidade lógica; `main.py` injeta o cliente.
- O cliente importa o módulo do `Protocol` e não herda dele. Só `main.py` importa o cliente, para I ficar em 0,50.
- Não criar import só para mudar a fórmula.

## Critério de pronto

Na `main`, nenhum componente fica ao mesmo tempo com A < 0,5, I < 0,5 e D >= 0,5, fora `schemas`. A suíte de caracterização passa na `v2-decoupled` sem diff contra a `v1-coupled`. O `grep` de modelo físico e de chave de provider em `app/` fica vazio.

## Handoff para o agente

O agente recebeu o plano de implementação já fechado com as decisões medidas, a suíte `pytest tests/characterization` e o comando `python metrics/measure.py <pasta-helpdesk> <nome>`. A suíte aceita ou rejeita mudança de comportamento. A métrica aceita ou rejeita a estrutura. O piloto abaixo foi medido antes de espalhar o mesmo desenho para as outras features.

## Piloto

Escopo: só a classificação. `classification.py` deixa de importar `llm` e `config` e passa a receber o `Protocol`. `main.py` injeta um cliente OpenAI concreto, que não passa por `llm.py`. As chaves dos providers continuam no serviço `app`, porque sugestão, relatório e extração ainda leem `config.py`.

Medição antes (`metrics/results/v1-coupled.csv`): `llm` Ca 4, Ce 1, I 0,20, D 0,80, na zona de dor. `classification` Ca 1, Ce 3, I 0,75, D 0,25.

Medição depois (`metrics/results/pilot-classification.csv`): `classification` Ca 1, Ce 2, I 0,67, D 0,33. `ports` Ca 2, Ce 0, A 1,00, D 0,00, fora da zona. `classification_client` Ca 1, Ce 2, I 0,67, D 0,33. `llm` Ca 3, Ce 1, I 0,25, D 0,75, ainda na zona. `config` segue com Ca 6, I 0,00, D 1,00.

## Aceite da refatoração escalada

O mesmo desenho foi para as quatro features, com um cliente único do gateway no lugar do cliente OpenAI do piloto. `pytest tests/characterization` passou sem alteração da suíte: o diff `v1-coupled` contra esta versão em `tests/characterization/` é vazio. A métrica em `metrics/results/v2-decoupled.csv` tira `llm` e `config` da zona porque os módulos deixaram de existir. `gateway` fica em I 0,50 e D 0,50, fora da zona. `schemas` continua nela e segue como exceção. O resultado foi aceito.

## Revisão

O piloto tirou a classificação de `llm.py`, e o Ca desse módulo caiu de 4 para 3. I subiu só de 0,20 para 0,25: sugestão, relatório e extração ainda importam o cliente concreto, então `llm` continua na zona de dor. `config` também permanece, porque o cliente do piloto assumiu o import que a classificação largou. Embrulhar `llm.py` não resolve. O passo seguinte apaga `llm.py`, `config.py` e `tickets.py`, e as quatro features passam a depender só do `Protocol`, com um único cliente do gateway injetado em `main.py`.
