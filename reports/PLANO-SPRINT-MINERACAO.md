# Plano do Sprint de Mineração — 3 semanas

**Período:** 2026-05-20 a 2026-06-10 (21 dias).
**Objetivo:** elevar o dataset de refatoração de 400 pares (insuficiente para todos os 5 smells) para uma cobertura suficiente para treinar 5 adapters LoRA, mantendo metodologia compatível com submissão futura a venues de pesquisa (MSR/ICSME/SANER).

---

## TL;DR

Foram considerados 5 caminhos para expandir o dataset. **Caminho 1 (LLM hybrid) foi descartado** por preferência metodológica. **Caminho 5 (rename-aware + cross-file extraction) foi acolhido** como contribuição publicável independente além de gerador de yield. **Caminhos 2, 3 e 4** entram em fases distintas. Para R2 especificamente, o adapter LoRA será encolhido (r=8 attention-only, 2,18M params) — única forma de manter os 5 smells sem LLM hybrid. R5 fica em "wait-and-see" até o checkpoint do dia 14.

A meta numérica esperada ao fim:

| Smell | Yield projetado | Adapter | Status |
|---|---:|---|---|
| R1 Extract Method | ~900-1.500 | r=16 full (18,46M) | ✓ atinge alvo recomendado |
| R3 Named Constant | ~330-530 | r=16 full | ✓ atinge alvo recomendado |
| R4 Guard Clauses | ~360-610 | r=16 full | ✓ atinge min viável |
| R5 Remove Dead Code | ~130-280 | a decidir dia 14 | contingente |
| R2 Parameter Object | ~110-270 | **r=8 attention-only (2,18M)** | min viável com adapter encolhido |

---

## 1. Contexto

### 1.1 De onde viemos

Histórico relevante (commits/PRs no repo `Gronoxx/tp-mineracao-manutencao`):

- **Plano 1** (anterior a este sprint): pipeline de 3 estágios implementado (keyword → candidato → verificação), curador Flask, Trilha B com LoRA, avaliação execution-based. 5 PRs.

- **Plano 2** (auditoria + correções): identificadas 5 findings críticas (F1-F5) + descobertas em execução (F6 dead_code ternário, F7 magic_numbers). 11 PRs (#8 a #17), 135 testes.

- **Plano 3** (produção): runner pronto para mineração em escala. 36 repos maduros, cap calibrado por LoRA (R1=4000, R2=3500, R3=1500, R4=2500, R5=2000), E1 permissivo ligado, resiliência. PR #19.

- **Mine de produção** (2026-05-19, ~42 min): produziu 400 pares (258 estritos + 142 parciais). Relatório completo em `reports/2026-05-20-mine-resultado.md`.

### 1.2 As metas de dados que precisamos atingir (literatura)

Um agente de pesquisa (Opus) sintetizou recomendações de literatura para Qwen2.5-Coder-1.5B + LoRA r=16, 7 módulos (18,46M params/adapter):

| Smell | Min viável | Recomendado | Max útil |
|---|---:|---:|---:|
| R1 Extract Method | 800 | 1.500–2.500 | 4.000 |
| R2 Parameter Object | 600 | 1.200–2.000 | 3.500 |
| R3 Named Constant | 200 | 500–800 | 1.500 |
| R4 Guard Clauses | 400 | 800–1.500 | 2.500 |
| R5 Remove Dead Code | 300 | 600–1.200 | 2.000 |

Bases (citáveis): LIMA (Zhou et al. 2023), QLoRA/Guanaco (Dettmers 2023), Raschka practical LoRA, CodeAlpaca. Regra `N ≥ k × params^0.25` para limites inferiores.

**Importante**: com rótulos parciais (E1 permissivo), multiplicar por 1,5-2× (literatura de noisy labels). Adapter encolhido (r=8) reduz fome de dado proporcionalmente.

### 1.3 O estado atual (mine de produção do dia 19)

| Smell | Total | Estritos | Parciais | % do min |
|---|---:|---:|---:|---:|
| R3 Named Constant | 129 | 73 | 56 | 64% |
| R4 Guard Clauses | 127 | 95 | 32 | 32% |
| R2 Parameter Object | 53 | 26 | 27 | 9% |
| R5 Remove Dead Code | 50 | 47 | 3 | 17% |
| R1 Extract Method | 41 | 17 | 24 | 5% |

**Diagnóstico**: yield natural é estruturalmente limitado. O pipeline exige (a) keyword na mensagem de commit, (b) mesma função no mesmo arquivo no `before` e `after`, (c) detector dispara antes E (estrito) não dispara depois OU (permissivo) magnitude reduzida ≥10%. Refatorações reais frequentemente envolvem rename + cross-file + multi-commit + sem keyword na mensagem — perdidas pelo pipeline atual.

---

## 2. As 5 estratégias consideradas

(Análise completa do agente de brainstorm em `reports/` — esta é a síntese para tomada de decisão.)

### Caminho 1 — Hybrid LLM-generate + detector-verify

LLM gera pares candidatos ancorados em cabeçalhos reais de função; nosso detector valida. Não é augmentação sintética pura porque o detector enforce o smell-pattern estaticamente. Yield estimado pra R2: 500-2.000.

**Status no sprint**: **DESCARTADO**. Preferência metodológica do Gustavo por dado real. Permanece como fallback se R2 falhar no Caminho 5 (revisão na semana 2).

### Caminho 2 — Mineração via PR-label do GitHub

Em vez de filtrar commits por keyword na mensagem, busca PRs marcados com labels `refactoring/cleanup/code-quality/tech-debt`. Cada PR vira 1 diff (multi-commit colapsado). Yield estimado: +200-800 R1, +50-300 R2, centenas em R3/R4/R5.

**Status no sprint**: **ACEITO**. Implementação na semana 2 (depende de C5 estar pronto para extração relaxada).

### Caminho 3 — Ingerir oracles existentes

Datasets públicos: PyRef (~15 R1 + ~12 outros), ActRef (167 R1 + outros, replication package a confirmar), maldil/RefactoringMiner (19 tipos), Sourcery (dead-code + guard-clause + R3). Três usos: (a) ingestão direta como pares de treino, (b) mineração adjacente (re-rodar nosso pipeline nos commits citados), (c) few-shots para C1.

**Status no sprint**: **ACEITO COM RESTRIÇÃO**. Por causa do gap de sourcing (ver §3), os pares de oracle vão pro **test set held-out**, não pro train. A mineração adjacente (nosso pipeline nos commits citados) entra no train com source tagged.

### Caminho 4 — Java→Python translation

SWE-Refactor (441 EM Java) + MaRV (693 pares Java) traduzidos pra Python via LLM, par-a-par, filtrados pelo nosso detector. Yield estimado: +250-350 R1.

**Status no sprint**: **ACEITO SÓ PARA R1**. R2 fica fora por baixa qualidade de tradução (Java POJO ≠ Python dataclass idiomático). R3/R4/R5 menos urgentes.

### Caminho 5 — Upgrade do pipeline (rename-aware, cross-file, multi-commit)

Três sub-melhorias: (a) colapso PR→1 diff, (b) drop keyword filter, (c) AST similarity matching para parear funções renomeadas/movidas. Yield estimado: +200-700 em R1, +50-200 em R2, centenas em R3/R4/R5.

**Status no sprint**: **ACEITO E PRIORIZADO**. Contribuição publicável independente ("primeiro miner Python open-source com extração rename-aware"). Custo realista com IA-assist: 5-8 dias focados.

---

## 3. Decisões estratégicas tomadas

| ID | Decisão | Justificativa |
|---|---|---|
| **D1** | Manter os 5 smells (não dropar R2 nem R5) | Cobertura completa do escopo original; defensável academicamente com adapter sizing diferenciado |
| **D2** | Adapter R2 encolhido (r=8 attention-only, 2,18M params) | Única forma de fazer R2 caber em ~150-270 pares sem usar LLM hybrid; literatura sustenta sample-efficiency scaling |
| **D3** | R5 mantém adapter cheio por enquanto; decisão deferida ao dia 14 | Yield R5 é incerto; melhor decidir com dado real em mãos |
| **D4** | Sem LLM hybrid (Caminho 1 descartado) | Preferência metodológica por dado real; também alinhado com publication track (reduz crítica de "synthetic data") |
| **D5** | Source tagging desde dia 1 | Separar pares de oracle (held-out) de pares minerados (train) sem misturar — evita retrabalho pra publicação |
| **D6** | Manter 36 repos maduros, sem escalar | Qualidade de dado > volume; repos menos maduros introduziriam ruído |
| **D7** | C4 (Java→Python) só para R1 | Tradução Java→Python falha em R2 (POJO ≠ dataclass); funciona bem para refators estruturais |
| **D8** | Alvo de longo prazo é publicação (MSR/ICSME/SANER) | Decisão de processo: usar publicação como guide, sem fazer todas as análises agora |

---

## 4. Execução — semana a semana

### Semana 1 (Dias 1-7) — Fundação + C3 + C5 base

**Objetivo**: schema atualizado, oracles ingeridos, C5a/b/c.1/c.2 implementados.
**Snapshot esperado fim da semana**: ~700-1.000 pares totais.

#### Dia 1 — Schema + diretórios

Branch: `feature/source-tagging`.

Tarefas:
1. Adicionar campo `source` em `core/schema.py`:
   ```python
   source: Optional[Literal[
       "mined_commit",     # nosso pipeline em commit individual (default)
       "mined_pr",         # nosso pipeline em PR colapsado (C2)
       "adjacent_oracle",  # nosso pipeline em commit citado por oracle (C3)
       "translated_java",  # tradução de SWE-Refactor/MaRV (C4)
   ]] = "mined_commit"
   ```
2. Criar diretório `data/test/` para held-out oracle pairs. Adicionar a `.gitignore` se necessário.
3. Backfill: marcar os 400 pares existentes em `data/raw/*.jsonl` com `source="mined_commit"`.
4. Testes em `tests/test_schema.py` para o novo campo.
5. Commit + push + PR + merge.

Deliverable: PR mesclada, schema atualizado, 400 pares marcados.

#### Dia 2 — C3 ingestão (oracles como held-out test)

Branch: `feature/c3-ingestao-oracles`.

Tarefas:
1. Pull PyRef CSV de `https://github.com/PyRef/PyRef/blob/main/data/dataset.csv`.
2. Adapter PyRef CSV → schema `RefactoringPair` → grava em `data/test/oracle_pyref_test.jsonl`.
3. Pull Sourcery examples de `sourcery-ai/examples`. Adapter → `data/test/oracle_sourcery_test.jsonl`.
4. Email aos autores do ActRef (arXiv 2505.06553) pedindo replication package (paralelo, blocking não).
5. Testes de carregamento. Commit + PR + merge.

Deliverable: `data/test/` populado, sem mexer em `data/raw/`.

#### Dia 3 — C3 adjacent mining

Branch: `feature/c3-adjacent-mining`.

Tarefas:
1. Extrai lista de commits citados em PyRef CSV.
2. Script que, pra cada commit, roda `mine()` com `partial_threshold=0.1` naquele commit hash (janela ajustada com `since`/`to` próximos).
3. Marca `source="adjacent_oracle"` nos pares gerados.
4. Mescla em `data/raw/` (F1 da PR #11 garante dedup).
5. Análise: quantos pares foram adicionados, distribuição por smell.

Deliverable: yield esperado +50-150 pares. Snapshot intermediário.

#### Dia 4 — C5a + C5b (multi-commit + drop keyword)

Branch: `feature/c5a-multicommit-c5b-drop-keyword`.

Tarefas:
1. Em `extracao/mineracao/minerador.py`:
   - Nova função `mine_pr(repo_url, output_path, pr_number, ...)`: clona o repo, descobre o merge commit do PR, faz diff `base..head`, processa como um único candidate batch.
   - Em `mine()`: nova flag `require_keyword: bool = True`. Quando `False`, pula o filtro `matched_keywords(commit.msg)`.
2. Testes em `tests/test_minerador_pr_mode.py`.
3. Smoke em 3 repos pequenos (flask, click, requests) — sem keyword filter, ver yield delta vs commit-mode.

Deliverable: pipeline aceita modo PR e modo "drop keyword". Yield em smoke documentado.

#### Dia 5 — C5c.1 (git --follow + file rename tracking)

Branch: `feature/c5c1-rename-aware-files`.

Tarefas:
1. PyDriller `ModifiedFile.change_type` retorna `RENAME` quando há rename detectado pelo git. `old_path` e `new_path` ficam disponíveis.
2. Em `extract_candidates`: tratar `RENAME` como caso especial — considerar funções com mesmo nome ENTRE arquivos diferentes (`new_path` ≠ `old_path` mas funções correspondentes).
3. Testes com repo git local (igual ao do `test_minerador_cap.py` com 8→1 params, mas agora movendo a função pra outro arquivo).

Deliverable: pipeline detecta refatorações com file rename.

#### Dia 6-7 — C5c.2 (AST similarity matching)

Branch: `feature/c5c2-ast-similarity`.

Tarefas (Dia 6):
1. Instalar lib `apted` (tree-edit-distance).
2. Função `_ast_similarity(fn1_source, fn2_source) -> float`: parseia ambas, converte para árvores APTED, computa edit distance, normaliza por tamanho.
3. Pre-filter via shape hash (número de statements, parâmetros, depth) — O(n) para descartar pares óbviamente diferentes antes do APTED O(n²).
4. Em `extract_candidates`: novo modo "cross-file similarity" — quando uma função desaparece no `before` e uma função com ≥0.7 similaridade aparece no `after`, parear como candidato.

Tarefas (Dia 7):
5. Testes com pares conhecidos (rename trivial + função similar mas com vars renomeadas).
6. Calibração do threshold: rodar em 50 pares conhecidos (PyRef oracle), medir precision em 5 valores de threshold (0.5, 0.6, 0.7, 0.8, 0.9). Pick o threshold com precision > 0.7.
7. Smoke em 3 repos. Tempo de execução comparado ao modo só-same-file.

Deliverable: pipeline detecta cross-file pairing. Precision documentada.

**Snapshot Sábado dia 7** — atualizar `reports/PROGRESSO-SPRINT-MINERACAO.md`:
- Yield atual por smell × source.
- Threshold calibrado.
- Decisões da semana.
- Próximas tarefas.

---

### Semana 2 (Dias 8-14) — Mitigações + C2 + mass mine

**Objetivo**: defesas contra falsos positivos, integração com PR mining, mass mine #2.
**Snapshot esperado fim da semana**: ~1.500-2.500 pares totais. **Checkpoint crítico R5 no dia 14.**

#### Dia 8 — C5c.3 (identifier overlap mitigation)

Branch: `feature/c5c3-identifier-overlap`.

Tarefas:
1. Função `_identifier_overlap(fn1_source, fn2_source) -> float`: extrai nomes de variáveis livres + nomes de funções chamadas em cada uma; computa Jaccard.
2. Em `extract_candidates`, no modo cross-file: rejeita par se overlap < 0.5 (mesmo que AST similarity > 0.7). Combate FP em funções "estruturalmente similares mas semanticamente diferentes" (e.g., dois `_validate_input` em domínios diferentes).
3. Testes com pares positive (mesma função renomeada) e negative (funções de domínios diferentes mas estrutura similar).

Deliverable: filtro adicional implementado.

#### Dia 9 — C5c.4 (behavioral validation amostrada)

Branch: `feature/c5c4-behavioral-validation`.

Tarefas:
1. Função `_behavioral_check(fn1_source, fn2_source) -> bool`: usa `hypothesis` para gerar 10 inputs sintéticos, executa ambas as funções, compara outputs.
2. Aplicação em **amostra** (não em todos os pares): tirar 50 pares cross-file aleatórios, rodar check, medir taxa de aprovação.
3. Calibração: se taxa de aprovação > 70%, o pipeline cross-file está confiável. Se < 50%, refinar threshold de AST similarity ou identifier overlap.

Deliverable: precision do cross-file matching medida empiricamente.

#### Dia 10-11 — C2 (GitHub PR mining via GraphQL)

Branch: `feature/c2-pr-mining-graphql`.

Tarefas (Dia 10):
1. Setup PAT (Personal Access Token fine-grained) com escopo `public_repo` (read).
2. Script `extracao/execucao/pr_search.py`: usa GraphQL `search(type: ISSUE)` para enumerar PRs com queries shardadas:
   ```
   is:pr is:merged label:refactoring language:python created:2020-01-01..2020-12-31
   ```
   (shard por ano, por label variant: refactoring/cleanup/code-quality/tech-debt/refactor).
3. Coleta `(repo, pr_number, base_sha, head_sha, files_changed)`.
4. Persistência em `data/pr_list.json` (cache para evitar requeries).

Tarefas (Dia 11):
5. Integração com `mine_pr()` do dia 4: para cada PR do cache, chama `mine_pr()` e mescla resultado em `data/raw/` com `source="mined_pr"`.
6. Smoke em 5 PRs conhecidos (escolher 5 PRs marcados refactor de repos diferentes), checar yield.

Deliverable: pipeline PR-mining integrado. Smoke documentado.

#### Dia 12 — Mass mine #2

Tarefas:
1. `rm -rf data/raw` (corrida fresca).
2. Backfill: ingere `data/test/oracle_*_test.jsonl` no test set sem misturar com raw.
3. Roda runner em modo combinado: commit-mode + PR-mode + drop-keyword. Todos os 36 repos. Cap dict de produção.
4. Background overnight. Log em `logs/mine-DAY12-DATE.log`.

Deliverable: nova rodada de mineração completa.

#### Dia 13 — Análise

Tarefas:
1. Script de análise: total por smell × source. Precision em amostra cross-file.
2. Yield comparado às metas:
   - R1: alvo 800 → temos X?
   - R2: alvo 600 (ou 290 com adapter encolhido r=16 attn, ou 140 com r=8 attn).
   - R3: alvo 200.
   - R4: alvo 400.
   - R5: alvo 300.
3. Relatório `reports/2026-XX-XX-mine-pos-c5.md`.

Deliverable: yield por smell quantificado.

#### Dia 14 — CHECKPOINT CRÍTICO R5

**Decisão obrigatória neste dia**, baseada no yield real de R5:

| Yield R5 | Decisão |
|---:|---|
| ≥ 300 | ✓ Mantém adapter cheio (r=16 full, 18,46M) |
| 150-299 | Encolhe adapter (r=16 attention-only, 4,36M) |
| 80-149 | Adapter mínimo (r=8 attention-only, 2,18M); aceita o limite |
| < 80 | Discussão: drop R5 do escopo, OU aceitar LLM hybrid SÓ pra R5 |

Documentar decisão no PROGRESSO.

**Atualizar `reports/PROGRESSO-SPRINT-MINERACAO.md`** com snapshot completo da semana 2.

---

### Semana 3 (Dias 15-21) — C4 + smoke training + entrega

**Objetivo**: C4 para R1, smoke trainings, documentação final, entrega.

#### Dia 15-16 — C4 (Java→Python translation para R1)

Branch: `feature/c4-java-translation`.

Tarefas (Dia 15):
1. Baixar SWE-Refactor de Zenodo 17196850. Filtrar para os 441 pares Extract Method.
2. Implementar `translate_java_pair(before_java, after_java) -> tuple[str, str]`: prompt LLM com instrução explícita "translate to idiomatic Python preserving the structural refactor difference".
3. Modelo: DeepSeek (`ensemble_runner.py single deepseek-chat` — T2/baixo custo).

Tarefas (Dia 16):
4. Loop de tradução com filtragem pelo detector:
   - Traduz cada par.
   - Parse Python do `before_translated`.
   - Detector `long_method` precisa disparar no `before_translated` (senão a tradução perdeu o sinal — descarta).
   - Detector não dispara no `after_translated`.
   - Marca `source="translated_java"`.
5. Mescla em `data/raw/`. Esperado: +250-350 R1.
6. Análise de qualidade em amostra: 20 pares traduzidos inspecionados manualmente.

Deliverable: yield R1 atualizado.

#### Dia 17 — Smoke training R2 (adapter encolhido r=8 attention-only)

Tarefas:
1. Configurar `LoRATrainingConfig` em `trilha_b/training/lora_config.py` com variant `r=8`, `target_modules=["q_proj", "v_proj", "k_proj", "o_proj"]` (só atenção, sem MLP).
2. Treinar 1 epoch em R2 (~150-270 pares disponíveis). Validation split 10%.
3. Loss curve: train vs eval. Sample outputs em 5 inputs de validação.
4. **Sanity check**: outputs fazem sentido como Parameter Object? Não decai HumanEval em mini-eval?
5. **Decisão**: se loss converge sem overfit visível → ✓ Caminho A confirmado. Se overfita em 1 epoch → reduzir ainda mais (r=4) ou aceitar limitação.

Deliverable: piloto R2 documentado. Decisão A vs fallback.

#### Dia 18 — Smoke training R5 (config conforme decisão do dia 14)

Tarefas:
1. Setup conforme decisão do dia 14.
2. Treino smoke análogo ao R2.
3. Loss curve + sanity check.
4. Decisão final R5.

Deliverable: piloto R5 documentado.

#### Dia 19-20 — Documentação + delivery prep

Tarefas:
1. README atualizado em `tp-mineracao-manutencao`:
   - Pipeline atualizado (commit-mode + PR-mode + cross-file).
   - Source tagging explicado.
   - Adapter sizing per smell (R2/R5 podem ter configs diferentes).
2. Relatório final em `reports/2026-XX-XX-sprint-final.md`:
   - Yield breakdown final (5 smells × estritos/parciais × source).
   - Precision cross-file medida.
   - Smoke training results.
   - Decisões tomadas durante o sprint.
3. Cleanup: branches mescladas, sem código órfão.

Deliverable: documentação completa, repo limpo.

#### Dia 21 — Buffer + entrega

- Margem para resolver imprevistos.
- Apresentação da entrega (formato a definir conforme requisitos da disciplina).

---

## 5. Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| C5 cross-file matching tem precision < 0.5 | Médio | Alto (poluição de dataset) | Gate de validação no dia 9 (behavioral check em amostra). Se < 50% fail, refinar threshold ou desabilitar cross-file. |
| R5 fica < 80 pares mesmo após C5+C2 | Médio | Alto (decisão de drop ou hybrid) | Checkpoint dia 14. Decisão documentada. |
| R2 com adapter encolhido não converge no smoke | Baixo-médio | Alto (Caminho A falha) | Fallback dia 17: reduz adapter ainda mais (r=4) ou aceita LLM hybrid pra R2 com curadoria pesada. |
| Mass mine #2 (dia 12) demora mais que esperado | Médio | Médio (atraso de 1-2 dias) | Mine #2 roda em background; análise (dia 13) é offline. |
| GraphQL API hit rate-limit | Baixo | Médio | PAT + sharding já implementado. GitHub App é fallback se necessário. |
| ActRef replication package não chega em tempo hábil | Médio | Baixo | C3 não depende disso (PyRef + Sourcery são suficientes). |
| SWE-Refactor zenodo indisponível | Baixo | Médio (perde C4) | C4 é "nice-to-have" pra R1; R1 já está em ~640-1240 sem C4. |
| Bug introduzido em C5 quebra suite de testes | Baixo | Médio | TDD: testes antes de mass mine. PR review opcional via skill `/thesis-code-review` se necessário. |

---

## 6. Critérios de "pronto" para a entrega

A entrega do sprint é considerada completa quando:

1. **Código**:
   - Caminhos 2, 3, 4, 5 implementados, testados, mesclados em `main`.
   - Suite de testes 100% verde (≥150 testes esperados).
   - Source tagging consistente em todos os pares de `data/raw/`.

2. **Dados**:
   - `data/raw/` com ≥ 1.500 pares total.
   - Cada smell com pelo menos:
     - R1 ≥ 800 (min viável)
     - R2 ≥ 140 (min viável com adapter encolhido r=8 attn)
     - R3 ≥ 200 (min viável)
     - R4 ≥ 400 (min viável)
     - R5 ≥ X (X conforme decisão do dia 14)
   - `data/test/` com oracle pairs separados, intocados pelo treino.

3. **Documentação**:
   - README atualizado.
   - `reports/2026-XX-XX-sprint-final.md` com yield breakdown, decisões, smoke training results.
   - `reports/PROGRESSO-SPRINT-MINERACAO.md` com log completo das sessões.

4. **Pilotos de treino**:
   - R2 smoke training executado, loss curve documentada, decisão A vs fallback formalizada.
   - R5 smoke training executado conforme decisão do dia 14.

---

## 7. Referências internas

- `extracao/execucao/mineracao.py` — runner de produção (PR #19).
- `extracao/mineracao/minerador.py` — engine de mineração com E1 (PR #18).
- `core/schema.py` — `RefactoringPair`; campo `source` a ser adicionado.
- `extracao/execucao/filtro_smells.py` — curador Flask com revisão dupla (PR #13).
- `reports/2026-05-20-mine-resultado.md` — resultado da mineração de produção.
- PRs mesclados: #8 (F5), #9 (F4+F3), #10 (justificativa), #11 (F1 merge), #12 (F2 curate.jsonl), #13 (revisão dupla), #14 (F6), #15 (F7), #16 (R5 AST), #17 (cap), #18 (E1), #19 (produção), #20 (relatório).

## 8. Referências externas

- **Pesquisa LoRA sizing**: relatório do agente Opus (não persistido — relevante: 18,46M params/adapter Qwen2.5-Coder-1.5B + r=16 full; per-smell recommendations em §1.2).
- **PyRef**: https://github.com/PyRef/PyRef + paper SCAM 2021.
- **ActRef**: arXiv 2505.06553 (replication package a confirmar via email).
- **maldil/RefactoringMiner Python**: https://github.com/maldil/RefactoringMiner.
- **Sourcery**: https://github.com/sourcery-ai/examples + PR search by author `sourcery-ai[bot]`.
- **SWE-Refactor**: arXiv 2602.03712 + Zenodo 17196850.
- **MaRV**: Zenodo 14450098.
- **refactoring.guru**: https://refactoring.guru/ — para few-shots canônicos.
- **CodeTracker** (rename-aware Java, port idea): arXiv 2409.16185.

---

## 9. Como usar este documento

Este é o documento de plano (estático após aprovação). **Atualizações vão para `PROGRESSO-SPRINT-MINERACAO.md`**. Mudanças neste plano só com decisão explícita do Gustavo + nota no documento de progresso.

**Sessão nova lê primeiro**: `PROGRESSO-SPRINT-MINERACAO.md` (estado atual). Recorre a este plano para entender o contexto e detalhes de execução de cada dia.
