# Dataset de Pares de Refatoração — Documentação de Metodologia e Origem

Este documento descreve a origem, metodologia de coleta e critérios de qualidade dos pares de treinamento para cada LoRA de refatoração (R1–R5).

---

## Visão Geral

Os pares estão em `trilha_b/data/sample_pairs/` no formato `RefactoringPair` (ver `core/schema.py`). Cada par contém `before_code` e `after_code` em Python, além de metadados de proveniência. O campo `source` identifica como o par foi obtido:

| `source` | Descrição |
|---|---|
| `mined_commit` | Minerado do histórico de commits de repos Python reais via PyDriller |
| `mined_pr` | Minerado de Pull Requests colapsados (estratégia C2) |
| `adjacent_oracle` | Commit citado por oracle externo, minerado por adjacência (C3) |
| `translated_java` | Par Java do dataset SWE-Refactor traduzido para Python via LLM (C4) |
| `cross_file` | Pareamento cross-file via similaridade AST (C5) |

---

## R1 — Long Method → Extract Method

**Arquivo:** `trilha_b/data/sample_pairs/r1_long_method.json`
**Total atual:** 98 pares

### Origem: Estratégia C4 — Tradução Java→Python

Os 98 pares foram gerados pela **estratégia C4**, que traduz pares Java do dataset [SWE-Refactor (Zenodo 17196850)](https://zenodo.org/records/17196850) para Python idiomático via LLM local.

**Dataset de origem:** SWE-Refactor contém 1099 pares de refatoração Extract Method de projetos Java open-source. Filtramos 350 pares com método `before` ≥ 10 linhas, cobrindo projetos como hibernate-orm, hibernate-search, javaparser, pmd, checkstyle, zxing, entre outros.

**Pipeline de geração:**

```
SWE-Refactor (350 pares Java)
        ↓
  Qwen2.5-Coder-7B-Instruct Q4_K_M
  (tradução Java → Python, ~20 tok/s)
        ↓
  Filtro de qualidade em duas camadas
        ↓
  98 pares válidos
```

**Filtro de qualidade (duas camadas):**

**Camada 1 — Detector estático (47 pares):**
O detector `detectores/long_method.py` (NLOC > 30 ou CC > 10 via lizard) é aplicado ao `before_py`. O par passa se:
- `before_py` possui ≥ 1 função com long_method detectado
- Função principal do `after_py` NÃO é long_method

**Camada 2 — LLM judge Gemma 4 26B Q3 (51 pares adicionais):**
Pares que falharam no detector estático por NLOC ≤ 30 (o threshold Java não se aplica diretamente ao Python, que é ~1.5× mais conciso) são avaliados pelo Gemma 4 26B Q3 como juiz subjetivo. O modelo recebe o par completo (`before_py` + `after_py`) e responde SIM/NÃO com justificativa de 1 linha, avaliando:
- Se o `before` é suficientemente longo/complexo para justificar a refatoração
- Se o `after` tem a função principal visivelmente menor, delegando a helpers extraídos

Os pares aprovados pelo LLM judge são marcados com `"llm_judge": true` para rastreabilidade na revisão manual.

**Distribuição dos 98 pares por projeto de origem:**

| Projeto | Pares |
|---|---|
| hibernate-orm | 22 |
| hibernate-search | 14 |
| javaparser | 11 |
| pmd | 10 |
| checkstyle | 9 |
| jadx | 6 |
| commons-io | 5 |
| hertzbeat | 5 |
| commons-lang | 4 |
| shenyu | 4 |
| zxing | 3 |
| mockito | 2 |
| junit5 | 1 |
| gson | 1 |
| shardingsphere-elasticjob | 1 |

**Tamanho dos pares gerados:**
- `before_py`: mediana 43L, mínimo 10L, máximo 159L
- `after_py`: mediana 33L, mínimo 4L, máximo 130L

**Modelos utilizados:**
- Tradução: `qwen2.5-coder:7b-instruct-q4_K_M` (Ollama local, ~20 tok/s)
- Fixação de `after` longo: `batiai/gemma4-26b:q3` (Extract Method focado, `think=False`)
- Juiz de qualidade: `batiai/gemma4-26b:q3` (avaliação subjetiva do par completo)

**Scripts:**
- `smoke_c4/batch_translate.py` — tradução em batch
- `smoke_c4/fix_after_gemma.py` — fixação dos `after` ainda longos
- `smoke_c4/llm_judge.py` — julgamento subjetivo pelo Gemma

**Nota sobre revisão manual:** Os 51 pares aprovados pelo LLM judge (`"llm_judge": true`) devem ter prioridade de revisão humana, pois seu critério de qualidade é subjetivo. Os 47 aprovados pelo detector estático passaram por critério objetivo (NLOC/CC).

---

## R2 — Long Parameter List → Introduce Parameter Object

**Arquivo:** `trilha_b/data/sample_pairs/r2_long_params.json`
**Total atual:** 4 pares

### Origem: Exemplos sintéticos (placeholder)

Os 4 pares atuais são **exemplos sintéticos** criados manualmente como fixtures de desenvolvimento, identificados por `"repo": "example"`. Representam o schema correto mas não são dados de treinamento reais.

**Plano de expansão:** Mineração via PyDriller (`source: "mined_commit"`) em commits que introduzem dataclasses ou objetos de configuração. Palavras-chave de busca: "introduce parameter object", "replace params with", "create config", "add dataclass". Oracles externos: pyref e sourcery (ver `data/test/`).

---

## R3 — Magic Numbers/Strings → Named Constants

**Arquivo:** `trilha_b/data/sample_pairs/r3_magic_numbers.json`
**Total atual:** 4 pares

### Origem: Exemplos sintéticos (placeholder)

Os 4 pares atuais são **exemplos sintéticos** com `"repo": "example"`. Fixtures de desenvolvimento apenas.

**Plano de expansão:** Mineração em commits que extraem constantes módulo-nível (padrão `ALL_CAPS = valor`). Palavras-chave: "extract constant", "magic number", "named constant", "replace literal". Detector estático (ruff PLR2004) pode pré-filtrar candidatos.

---

## R4 — Deep Nesting → Guard Clauses

**Arquivo:** `trilha_b/data/sample_pairs/r4_deep_nesting.json`
**Total atual:** 4 pares

### Origem: Exemplos sintéticos (placeholder)

Os 4 pares atuais são **exemplos sintéticos** com `"repo": "example"`. Fixtures de desenvolvimento apenas.

**Plano de expansão:** Mineração em commits que reduzem profundidade de aninhamento via early return / inversão de condição. Palavras-chave: "guard clause", "early return", "reduce nesting", "invert condition". Detector pylint R1702 pode pré-filtrar.

---

## R5 — Dead Code → Remove

**Arquivo:** `trilha_b/data/sample_pairs/r5_dead_code.json`
**Total atual:** 5 pares

### Origem: Exemplos sintéticos (placeholder)

Os 5 pares atuais são **exemplos sintéticos** com `"repo": "example"`. Fixtures de desenvolvimento apenas.

**Plano de expansão:** Mineração em commits com mensagens de remoção de dead code. Palavras-chave: "remove dead code", "remove unused", "cleanup", "remove unreachable". Ferramentas: vulture, pylint W0101/W0612 para pré-filtragem.

---

## Oracles externos (conjunto de teste)

Os oracles em `data/test/` são usados exclusivamente como **conjunto de teste held-out** — não entram no treinamento.

| Arquivo | Origem | Uso |
|---|---|---|
| `oracle_pyref_test.jsonl` | PyRef — ferramenta de detecção de refatorações Python | Avaliação de R1–R5 |
| `oracle_sourcery_test.jsonl` | Sourcery — assistente de refatoração Python | Avaliação de R1–R5 |
| `oracle_pyref_test.csv` | Versão CSV do oracle PyRef | Análise exploratória |

---

## Critérios gerais de qualidade

Todo par, independente da origem, deve satisfazer:

1. **Parseabilidade:** `before_code` e `after_code` são Python válido (`ast.parse()` sem erro)
2. **Não-trivialidade:** `before_code` e `after_code` são diferentes
3. **Smell detectável no before:** o detector do smell correspondente dispara em `before_code`
4. **Smell resolvido no after:** o detector não dispara (ou dispara com magnitude reduzida, `partial=True`) em `after_code`
5. **Preservação de intent:** a lógica principal é preservada — não é reescrita completa

Para R1 especificamente, o critério 3 e 4 é verificado pelo detector estático (NLOC/CC via lizard) ou, quando o threshold estático é muito restritivo para Python, pelo LLM judge (campo `llm_judge: true`).
