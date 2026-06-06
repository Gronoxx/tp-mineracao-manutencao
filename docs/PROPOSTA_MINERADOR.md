# Proposta — Minerador de pares de refatoração (R1–R5)

> **Status:** implementado · maio 2026 · repo `tp-mineracao-manutencao`
> **Natureza:** este documento descreveu a direção do minerador; o pipeline foi
> implementado nos PRs #3 (schema `core/`), #6 (minerador — estágios 1–3) e #7
> (curador — estágio 4). As seções abaixo descrevem o desenho; as notas
> **Implementado** apontam onde cada parte vive no código.

---

## 1. Contexto e objetivo

O escopo do TP foi consolidado em 07/05/2026 (`ESCOPO_E_TRILHAS`): **9 smells
detectados por regras estáticas, 5 com refatoração automática via LoRA**
(R1–R5). O minerador existe para **uma coisa só**: produzir os dados de treino
desses 5 LoRAs de refatoração.

| LoRA | Refatoração | Smell |
|---|---|---|
| R1 | Extract Method | Long Method |
| R2 | Introduce Parameter Object | Long Parameter List |
| R3 | Replace with Named Constant | Magic Numbers |
| R4 | Guard Clauses | Deeply Nested Conditional |
| R5 | Remove | Dead Code |

**Os 4 smells sem LoRA** (Refused Bequest, Duplicate Code, Long Message Chain,
Middle Man) são *detecção apenas*: detectados por regra, reportados pela CLI com
sugestão textual, refatorados manualmente pelo usuário. **O minerador não os
toca** — regra não treina, e não há refatoração a gerar para eles.

O minerador entrega **pares verificados (antes, depois)**. A conversão em
exemplos `prompt/completion` é a curadoria da Trilha B, não do minerador.

---

## 2. Por que redesenhar o minerador atual

O minerador atual (`extracao/mineracao/minerador.py`) é um bom rascunho, mas tem
problemas que comprometem a qualidade do dataset — e o dataset alimenta direto o
treino da Trilha B:

- **O rótulo vem de palavra-chave na mensagem do commit.** É um proxy ruidoso:
  a mensagem é uma afirmação sobre o commit *inteiro*, não sobre a função.
- **A atribuição é por commit inteiro.** Toda função alterada, em todo arquivo
  do commit, recebe todos os smells casados — e um par casado em 2 smells é
  gravado 2× com rótulos `y` contraditórios.
- **Extract Method (R1) não é capturado.** O minerador indexa funções por nome;
  a função-helper extraída é nova, nunca é pareada, e o `after` sai incompleto.
- **`y` one-hot** é rótulo de classificador, num dataset de geração onde não
  serve; **modo append** duplica tudo a cada execução.

A proposta abaixo corrige isso.

---

## 3. O que desejamos — pipeline em 4 estágios

> commits → **(1) recall** → **(2) extração** → **(3) verificação por detector**
> → **(4) validação humana** → dataset rico

### Estágio 1 — Recall (palavra-chave, acelerador)

**O que:** PyDriller percorre os commits; o casamento de palavras-chave na
mensagem (`SMELL_KEYWORDS`) serve como pré-filtro de velocidade e como metadado.

**Por quê:** AST-diffar todo commit de 15–20 repos é caro; a palavra-chave
reduz o espaço de busca. Mas — **a palavra-chave não é o rótulo**. Ela só
decide *se vale olhar o commit*. Quem rotula é o estágio 3. A mensagem é
guardada como campo (`commit_msg`) porque o revisor humano precisa dela.

### Estágio 2 — Extração de pares candidatos

**O que:** para cada commit (sem merges, só `.py`, ignorando arquivos de teste),
montar pares antes/depois. A granularidade é **por smell**:

- **R2–R5** (Long Param, Magic, Deep Nesting, Dead Code): refatoração local →
  par **função-a-função** (casa funções por nome, pareia as que mudaram).
- **R1** (Extract Method): o `after` precisa da função encolhida **mais os
  helpers extraídos** → par `(função longa)` → `(função encolhida + funções
  novas do mesmo arquivo/commit)`.

**Por quê:** Extract Method, por definição, cria função nova; um par
função-a-função jogaria o helper fora. Para os outros 4 a refatoração é local e
o par função-a-função está correto.

### Estágio 3 — Verificação pelos detectores

**O que:** para cada par candidato, rodar o detector estático do smell. Aceitar
o par **somente se** o detector dispara no `before` **e não dispara** no
`after`.

**Por quê:** isto transforma o rótulo fraco (mensagem de commit) num **rótulo
estrutural verificado**. Resolve de uma vez a contaminação multi-smell (quem
rotula é o detector, par a par) e alinha o dataset de treino à mesma noção de
smell que a ferramenta usa em produção.

> **Não há circularidade.** Os detectores das Camadas 1/2 são *regras estáticas*
> — não são modelos, não consomem dado de treino. O que se treina com os dados
> minerados são os LoRAs *geradores* (R1–R5). O pipeline é um DAG:
> regras → filtram os pares → pares treinam os geradores.

Para R1, uma checagem extra: tem de existir ≥1 função nova **e** a função
encolhida deve chamá-la — senão não foi Extract Method, foi outra mudança.

### Estágio 4 — Validação humana de todo o dataset

**O que:** cada par que passa pelo estágio 3 é revisado por um humano, que dá um
veredito e, quando necessário, **isola o par puro**.

**Por quê:** o detector e o humano são os dois andares — não são redundantes.
O detector é precisão automática barata (tira o lixo óbvio, dá vazão). O humano
é o julgamento real: "é uma refatoração limpa? o `after` ficou bom?". E o ponto
central — **commits do mundo real misturam a refatoração com bug-fix ou
feature**; o revisor recorta o `before`/`after` para conter só a refatoração.
O minerador não faz isso; o humano sim. É isto que torna o dataset *mais rico*.

Esta etapa **já está prevista no `ESCOPO`**: são as tarefas "Curadoria do
dataset" da Trilha B (~25 h no total para R1–R5).

---

## 4. Formato dos dados

> **Implementado:** `core/schema.py` — o modelo Pydantic `RefactoringPair` é o
> contrato único entre as trilhas A e B (D-DEV-18). Um JSONL por smell em
> `data/raw/`; **sem `y`**.

Campos do registro:

```json
{
  "id": "<sha1 estável>",
  "smell_type": "R1",
  "before_code": "<source>", "after_code": "<unidade refatorada>",
  "repo": "pallets/flask", "commit_hash": "<hash>", "parent_commit": "<hash>",
  "file": "src/flask/app.py", "function_name": "Flask.dispatch_request",
  "commit_msg": "<mensagem completa>", "msg_keywords": ["extract method"],
  "n_functions_after": 3,
  "metrics_before": {"...": "evidência do detector"},
  "metrics_after":  {"...": "evidência do detector"},
  "verified": true,
  "detector_before": {"detected": true,  "evidence": {}},
  "detector_after":  {"detected": false, "evidence": {}},
  "review": {
    "status": null, "before_clean": null, "after_clean": null,
    "out_of_rule": false, "reviewer": null, "notes": "", "timestamp": null
  }
}
```

Justificativa dos campos não óbvios:
- **`id`** — dedup e split train/test (resolve o append não-idempotente);
  preenchido por hash se ausente.
- **`smell_type`** — código `R1..R5` (vocabulário canônico em `core/smells.py`).
- **`commit_msg` / `msg_keywords`** — o revisor humano precisa ver *por que* o
  par foi flagueado para julgá-lo.
- **`metrics_*` / `verified` / `detector_*`** — auditoria do estágio 3.
- **`review`** — preenchido no estágio 4 pelo curador. `status` ∈
  `clean | noisy | rejected`; `before_clean`/`after_clean` guardam o par
  isolado quando o revisor recorta mudanças não-relacionadas; `out_of_rule`
  marca pares que não seguem a regra de refatoração esperada (D-DEV-05).
- **sem `y`** — `y` one-hot é rótulo de *classificador*; R1–R5 são LoRAs de
  *geração*, cujo alvo é o texto `after_code`. Não há classificador treinado no
  escopo do TP.

---

## 5. Dimensionamento

Como **todo o dataset será validado manualmente** e o orçamento da Trilha B é
~25 h, o minerador **não pode despejar milhares de pares**. Deve mirar um
tamanho revisável — ordem de **algumas centenas por smell**. O filtro do
estágio 3 já enxuga; se ainda sobrar muito, aplicar um teto por smell +
amostragem estratificada (mesma lógica usada no seed da `NOTA_DADOS_NEGATIVOS`).

> **Implementado:** a ferramenta do estágio 4 é o curador
> `extracao/execucao/filtro_smells.py` — um servidor Flask que mostra o *diff*
> de cada par e registra o veredito (`clean`/`noisy`/`rejected`) num sidecar
> `data/reviews/<smell>.reviews.jsonl`, **sem nunca reescrever `data/raw/`**.
> No caso `noisy`, o revisor recorta o par puro em `before_clean`/`after_clean`.
> Não é o anotador web de smells aparentes (esse é de outro componente, a trava
> da §4 da `PROPOSTA`) — é uma ferramenta distinta, para os pares de refatoração.

---

## 6. Limitações reconhecidas

A transição "smell presente → ausente" prova que o smell sumiu, **não** que a
mudança preservou comportamento (essa garantia é a "trava de segurança",
Future Work 1). Um par minerado é um exemplo *plausível* de refatoração, não
*garantido*. Isto deve ir para "ameaças à validade" no relatório, mitigado
pela validação humana (estágio 4) e pela avaliação execution-based dos LoRAs.

---

## 7. Status

**Implementado** (maio 2026, repo `tp-mineracao-manutencao`):
- `core/` — schema unificado `RefactoringPair` + `core/smells.py` (PR #3).
- `extracao/mineracao/minerador.py` — estágios 1–3 (PR #6); runner
  `mineracao.py` com a lista de 16 repositórios.
- `extracao/execucao/filtro_smells.py` — curador, estágio 4 (PR #7);
  `visualizacao.py` atualizado.

Pendente:
- **Re-minerar:** rodar `python -m extracao.execucao.mineracao` para gerar o
  dataset real em `data/raw/`.
- **Curadoria** (Trilha B, ~25 h): revisar os pares no curador; integrar o
  `curate.py` para ler o sidecar de vereditos (só `status == clean`).
- **Decisões do trio em aberto:** protocolo de revisão do estágio 4 (simples
  vs. dupla com kappa) e tamanho-alvo por smell (teto/amostragem do estágio 3).
