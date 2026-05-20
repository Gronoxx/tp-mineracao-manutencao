# Progresso do Sprint de Mineração

**Período**: 2026-05-20 a 2026-06-10 (21 dias).
**Plano completo**: `reports/PLANO-SPRINT-MINERACAO.md` (ler em conjunto com este).

---

## ⚡ Como usar este documento (LEIA PRIMEIRO)

### Início de cada sessão nova

1. **Ler esta seção** (⚡ Como usar) e a seção **🎯 Estado Atual** abaixo.
2. **Ler a entrada mais recente em `📓 Log de Sessões`** (no fim do arquivo) para entender o que foi feito na última sessão e qual era o próximo passo.
3. **Conferir `🔀 Decisões Pendentes`** se houver itens bloqueando.
4. **Recorrer ao `PLANO-SPRINT-MINERACAO.md`** para detalhes de execução do dia atual (`§4. Execução`).
5. **Confirmar com o Gustavo** o plano da sessão antes de começar (a menos que o próximo passo seja inequívoco).

### Durante a sessão

- Foco no próximo passo concreto descrito em "Próxima ação".
- Atualizar **🎯 Estado Atual** quando algo muda (yield, branch, decisão).
- Anotar decisões novas em **🗂️ Decisões durante o sprint** (append-only).

### Fim de cada sessão (obrigatório)

1. **Atualizar `🎯 Estado Atual`** — dia, fase, yield, próxima ação.
2. **Adicionar nova entrada em `📓 Log de Sessões`** — data, atividades, resultado, bloqueadores, próxima ação.
3. **Snapshot de yield** se rodou mass mine ou análise — em `📊 Snapshots de yield`.
4. **Commit do PROGRESSO** (preferencialmente junto com qualquer outro PR da sessão; pode ser commit separado direto na main para PROGRESSO se não estiver mexendo em código).

---

## 🎯 Estado Atual (live)

> **Atualizar a cada sessão.**

### Onde estamos

- **Data da última atualização**: 2026-05-20 (sessão overnight em andamento)
- **Dia do sprint**: 5 ✓ (Dias 6-7 em fila — AST similarity)
- **Semana**: 1
- **Fase**: Execução — Dia 1 (source tagging) mergeado. Modo overnight/auto: avançar pelos Dias 2-7 enquanto destravar.

### Yield atual por smell

Pós-Dia 3 (C3 adjacent mining mesclado via PR #24): +25 pares `adjacent_oracle` em `data/raw/`.

| Smell | mined_commit | adjacent_oracle | Total | Min viável | % do min | Status |
|---|---:|---:|---:|---:|---:|---|
| R1 Extract Method | 41 | 1 | 42 | 800 | 5% | ✗ |
| R2 Parameter Object | 53 | 7 | 60 | 600 (140 c/ r=8 attn) | 10% (43%) | ✗ |
| R3 Named Constant | 129 | 12 | 141 | 200 | 70% | borderline ↑ |
| R4 Guard Clauses | 127 | 4 | 131 | 400 | 33% | ✗ |
| R5 Remove Dead Code | 50 | 1 | 51 | 300 | 17% | ✗ |
| **Total** | **400** | **25** | **425** | | | |

### Próxima ação concreta

**Dias 6-7 do sprint** — C5c.2 (AST similarity matching com APTED):

1. Branch `feature/c5c2-ast-similarity`.
2. `pip install apted` (ou fallback `zss` se C-ext falhar).
3. Função `_ast_similarity(fn1_source, fn2_source) -> float`: parseia, tree-edit distance, normaliza.
4. Pre-filter via shape hash (n_stmts, n_params, depth) — descarta pares óbvios em O(n).
5. Em `extract_candidates`: novo modo "cross-file similarity" — função desaparece no before, função com ≥0.7 similaridade aparece no after → pareia.
6. Calibrar threshold em 50 pares PyRef oracle (precision > 0.7).
7. Snapshot fim semana 1.
8. PR + merge.

(Detalhes em `PLANO-SPRINT-MINERACAO.md §4 Semana 1 Dia 6-7`.)

### Branch / PR ativo

(nenhum — Dia 5 mesclado via PR #26)

### Pendências / bloqueadores

- **Email aos autores do ActRef** (arXiv 2505.06553) — pendência humana do Gustavo, não bloqueia.

---

## 🔀 Decisões Pendentes (precisam decisão antes de avançar)

(Lista vazia no momento. Lista é populada quando aparece bloqueio que exige decisão Gustavo.)

| ID | Descrição | Quando | Status |
|---|---|---|---|
| (vazio) | | | |

---

## 🗂️ Decisões durante o sprint (append-only)

Decisões tomadas DURANTE a execução do sprint (≠ decisões do plano, que estão no `PLANO-SPRINT-MINERACAO.md §3`).

| Data | Decisão | Razão | Impacto |
|---|---|---|---|
| (vazio) | | | |

---

## 📊 Snapshots de yield

Snapshots gerados em pontos-chave do sprint.

### Snapshot pré-sprint (2026-05-19, mine de produção PR #19)

| Smell | Estritos | Parciais | Total |
|---|---:|---:|---:|
| R1 | 17 | 24 | 41 |
| R2 | 26 | 27 | 53 |
| R3 | 73 | 56 | 129 |
| R4 | 95 | 32 | 127 |
| R5 | 47 | 3 | 50 |
| **Total** | **258** | **142** | **400** |

Fontes: 35 repos minerados com sucesso (hypothesis falhou no clone por falta de git-lfs).

### Snapshot Fim Semana 1 (Dia 7)

*(a preencher após snapshot)*

### Snapshot Fim Semana 2 (Dia 14 — checkpoint crítico R5)

*(a preencher após snapshot)*

### Snapshot Final (Dia 21)

*(a preencher após snapshot)*

---

## 📓 Log de Sessões

> **Template para nova entrada (copiar e colar):**
>
> ### Sessão N — YYYY-MM-DD
>
> **Duração estimada**: X horas.
> **Dia do sprint**: N de 21.
>
> **Atividade**:
> - (o que foi feito)
>
> **Resultado**:
> - (saída concreta — PRs mesclados, yield gerado, etc.)
>
> **Bloqueadores**:
> - (se houver)
>
> **Próxima ação**:
> - (passo concreto para a próxima sessão)
>
> **Notas**:
> - (qualquer coisa que vale registrar — surprise, ajuste de threshold, observação)

---

### Sessão 6 — 2026-05-20 (Dia 5 — C5c.1 file rename tracking)

**Duração estimada**: ~25 min.
**Dia do sprint**: 5 de 21.
**Modo**: overnight / auto-mode.

**Atividade**:
- Investigação: testei o comportamento atual do `mine()` em fixture local com `git mv` + refactor. PyDriller detecta `ModificationType.RENAME` quando a similaridade entre old/new é alta (>50%) e entrega `source_code_before`/`source_code` no mesmo `ModifiedFile`. `extract_candidates` já casa funções por nome — sem lógica especial necessária.
- `extracao/mineracao/minerador.py`: comentário em `extract_candidates` documentando a propriedade RENAME-aware e apontando para testes.
- `tests/test_minerador_rename.py`: 3 testes (RENAME+R2, RENAME+R1, ADD+DELETE como limite documentado).
- Fixture-craft: precisei de ~160 linhas comuns (80 funcs util idênticas) para manter similaridade > 50% no R1 case (que muda foo drasticamente).
- PR #26 criado, mesclado via squash (commit `04eb93b`).

**Resultado**:
- ✓ Cobertura de regressão para o caso RENAME-aware.
- ✓ Limite atual documentado: ADD+DELETE separados (similaridade baixa) NÃO produzem par — fica para Dia 6-7 (AST similarity cross-file).
- ✓ `pytest tests/ -q` → **171 passing** (168 + 3).

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 6-7** — C5c.2 AST similarity matching (APTED).

**Notas**:
- Dia 5 acabou sendo "menor" que o esperado: o trabalho real já estava no PyDriller. O valor agregado foi cobertura de testes + documentação do comportamento + identificação clara do limite (cross-file sem rename).
- Caso interessante para o snapshot do Dia 7: medir quantos dos pares de `data/raw/` vieram de commits com RENAME — daria ideia da contribuição real desse mecanismo. Adicionado como item informal.

---

### Sessão 5 — 2026-05-20 (Dia 4 — C5a mine_pr + C5b require_keyword)

**Duração estimada**: ~30 min.
**Dia do sprint**: 4 de 21.
**Modo**: overnight / auto-mode.

**Atividade**:
- C5b — `require_keyword: bool = True` adicionado em `mine()`. Default preserva comportamento; quando `False`, pula `matched_keywords()` no loop.
- C5a — `mine_pr(repo_url, output_path, merge_commit_shas, ...)` adicionada. Thin wrapper sobre `mine_specific_commits` (Dia 3) com `only_no_merge=False` e `source="mined_pr"`. `mine_specific_commits` ganhou kw `only_no_merge: bool = True` para suportar o caso PR.
- `tests/test_minerador_pr_mode.py`: 7 testes (3 require_keyword, 4 mine_pr). Fixture local com squash merge valida que mine_pr processa o PR como diff único.
- Smoke em flask/click/requests deferido (alto custo de rede overnight; testes unitários cobrem correção; yield delta será medido no mass mine #2 do Dia 12).
- PR #25 criado, mesclado via squash (commit `3f0c7fc`).

**Resultado**:
- ✓ `mine()` aceita `require_keyword=False` — destrava mineração em janelas curtas (será usado pelo Dia 10-11 C2 PR mining).
- ✓ `mine_pr()` disponível — pronto para o pipeline GraphQL do Dia 10-11 popular `merge_commit_shas`.
- ✓ `pytest tests/ -q` → **168 passing** (161 + 7).
- ✓ Os 3 caminhos do minerador agora prontos: keyword-mine (`mine`), commit-list (`mine_specific_commits`), PR-mode (`mine_pr`).

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 5** — C5c.1 file rename tracking. Tratar `RENAME` em `extract_candidates`.

**Notas**:
- Decisão: `mine_pr` não resolve PR → SHA. O caller (futuro runner do Dia 10-11) faz a resolução via `gh pr view <N> --json mergeCommit.oid`. Isso mantém o minerador puro e testável offline.
- Fixture do teste mine_pr usa squash merge (`git merge --squash`) — modo mais comum em PRs GitHub. True merges (`--no-ff`) também funcionam (PyDriller diffa contra primeiro parent), mas o caso de teste mais útil é o squash.

---

### Sessão 4 — 2026-05-20 (Dia 3 — C3 adjacent mining)

**Duração estimada**: ~50 min (incluindo execução do mining em background).
**Dia do sprint**: 3 de 21.
**Modo**: overnight / auto-mode.

**Atividade**:
- `extracao/mineracao/minerador.py`: adicionado kw `source="mined_commit"` em `verify_pair()` (passthrough → `RefactoringPair.source`). Nova função `mine_specific_commits(repo_url, output_path, commit_hashes, partial_threshold=0.1, source="adjacent_oracle", clone_repo_to=None)` que usa `only_commits` do PyDriller e BYPASSA o filtro de keyword.
- `scripts/c3_adjacent_mining.py`: lê `data/test/oracle_pyref_test.jsonl`, agrupa por repo (3 únicos), dispara `mine_specific_commits` em cada um com cache de clones em `/tmp/c3_adjacent_clones/`.
- `tests/test_mine_specific_commits.py`: 6 testes (bypass keyword, source tag default, source customizável, lista vazia, filtro por hash, idempotência).
- Execução em background: 3 repos, 234 commits únicos, 44s total. 25 pares produzidos (R1=1, R2=7, R3=12, R4=4, R5=1).
- PR #24 criado, mesclado via squash, main sincronizada (commit `9c3dee7`).

**Resultado**:
- ✓ `data/raw/` passou de 400 → 425 pares.
- ✓ Source tags propagadas: 400 mined_commit + 25 adjacent_oracle (todos os 5 arquivos jsonl consistentes).
- ✓ `pytest tests/ -q` → **161 passing** (155 + 6).
- ✓ Função `mine_specific_commits` reutilizável para fontes futuras (ActRef, SWE-Refactor).

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 4** — C5a (mine_pr) + C5b (drop keyword flag em `mine()`).

**Notas**:
- Yield observado (+25) ficou abaixo da estimativa do plano (+50-150). Razão provável: PyRef catalogou só 3 repos relativamente pequenos/médios. Mesmo com `partial_threshold=0.1` (modo permissivo), a maioria dos commits PyRef dispara em poucos pares.
- Decisão de design: bypassar o filtro de keyword no caminho `adjacent` foi uma escolha consciente — esses commits já são refatorações validadas; aplicar keyword filter perderia commits que PyRef validou. (Aprendizado: a função keyword é pré-filtro de recall para mineração CEGA, não rótulo.)
- `mine_specific_commits` é genérica em `source`: aceita qualquer das 4 tags do schema. Reaproveitável quando ActRef/SWE-Refactor chegarem.

---

### Sessão 3 — 2026-05-20 (Dia 2 — C3 ingestão oracles)

**Duração estimada**: ~40 min.
**Dia do sprint**: 2 de 21.
**Modo**: overnight / auto-mode.

**Atividade**:
- Investigação das fontes: PyRef CSV (573 linhas, só metadata — sem código) e Sourcery examples (refactorings/basic_examples.py + extract_examples.py — só "before").
- Decisão de escopo (auto-mode, sem replanejar): em vez de clonar ~25 repos para extrair before/after overnight (risco operacional), criar `OracleEntry` como modelo metadata-only. A extração de código real fica para Dia 3 (adjacent mining), que já é o passo seguinte do plano.
- `core/oracle.py`: novo modelo `OracleEntry` (Pydantic BaseModel) — fields: source_dataset, external_refactoring_type, validation, repo, commit_hash, file, function_name, smell_type, description, tool, notes.
- `scripts/ingest_oracles.py`: adapter PyRef CSV + Sourcery .py → OracleEntry. Mapeia "Extract Method"/"Inline Method" → R1; demais → None (catálogo bibliográfico).
- `.gitignore`: padrão alterado de `data/` para `data/**` + exceções `!data/test/`, `!data/test/**` (git não re-inclui se pai está ignorado).
- Geração do catálogo: 573 PyRef + 10 Sourcery = 583 entradas em `data/test/`.
- `tests/test_oracle_ingest.py`: 12 testes (schema OracleEntry, parsers de URL/description, ingestão end-to-end com fixtures temporárias, sanity check do catálogo real).
- PR #23 criado, mesclado via squash, main sincronizada (commit `d624221`).

**Resultado**:
- ✓ Catálogo de oracles versionado em `data/test/`.
- ✓ **573 entradas PyRef** (451 TP, 114 FP, 8 CTP) — **25 entradas R1+TP** (material primário para teste held-out de R1).
- ✓ **10 entradas Sourcery** (catálogo bibliográfico, smell_type=None).
- ✓ `.gitignore` permite versionar `data/test/`, mantém `data/raw/` ignorado.
- ✓ `pytest tests/ -q` → **155 passing** (143 + 12).
- ✓ PR #23 mesclado.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 3** — C3 adjacent mining. Branch `feature/c3-adjacent-mining`. Ler `data/test/oracle_pyref_test.jsonl`, extrair `commit_hash`, rodar `mine()` em cada commit (partial_threshold=0.1), marcar `source="adjacent_oracle"`, mesclar em `data/raw/`.

**Notas**:
- PyRef CSV não tem código (só commit URL + tipo). Plano literal pediu "PyRef CSV → schema RefactoringPair" mas isso é incompatível com o schema (before/after são required, non-empty). OracleEntry como modelo separado é a solução limpa.
- Mapeamento PyRef → smells é parcial: só Extract Method (R1) tem correspondente direto. R2-R5 ficam sem entrada direta de PyRef; outros oracles (Sourcery, ActRef, SWE-Refactor) podem preencher esse gap.
- Sourcery examples são *demos* (input only). Para virar oracle de teste, precisaria executar Sourcery → fora de escopo overnight.
- gh CLI continua exigindo `git branch --set-upstream-to` após push via URL-com-token. Workaround confirmado.

---

### Sessão 2 — 2026-05-20 (Dia 1 — source tagging)

**Duração estimada**: ~30 min (estimado original: 45-75 min — execução foi mais rápida que o buffer).
**Dia do sprint**: 1 de 21.
**Modo**: overnight / auto-mode declarado pelo Gustavo (avançar continuamente sem pausa).

**Atividade**:
- Sanity check inicial: `pytest tests/ -q` → 140 passing, main sincronizada.
- Branch `feature/source-tagging` criada.
- `core/schema.py`: adicionado campo `source: Optional[Literal[...]] = "mined_commit"` no bloco "preenchido pelo minerador", entre `n_functions_after` e `review`.
- `tests/test_schema.py`: 3 testes novos (default `mined_commit`, aceita os 4 valores válidos, rejeita inválido via `pydantic.ValidationError`).
- `scripts/backfill_source.py`: utilitário idempotente — itera `data/raw/*.jsonl`, adiciona `"source": "mined_commit"` onde faltar, regrava. Reporta total/já-taggeados/atualizados por arquivo.
- `data/test/` criado vazio (gitignored — exceção fica para o Dia 2 quando houver conteúdo).
- Backfill executado: 5 arquivos, 400 registros, 400 atualizados. Idempotência confirmada (segunda execução: 0 atualizados).
- PR #22 criado, mesclado via squash, branch deletada, main sincronizada (commit `4173f21`).

**Resultado**:
- ✓ Schema atualizado com campo `source`.
- ✓ 400 pares em `data/raw/*.jsonl` taggeados localmente com `source="mined_commit"`.
- ✓ `data/test/` existe localmente, pronto para receber oracles no Dia 2.
- ✓ `pytest tests/ -q` → **143 passing** (140 + 3 novos).
- ✓ PR #22 mesclado.
- ✓ Smoke load via `RefactoringPair.model_validate_json` confirmado em `long_method.jsonl` (41 pares carregados sem erro).

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 2 do sprint** — C3 ingestão de oracles. Branch `feature/c3-ingestao-oracles`. PyRef CSV + Sourcery examples → `data/test/oracle_*_test.jsonl`. Exceção em `.gitignore` para `!data/test/`. Testes de carregamento. PR + merge. Sessão overnight continua sem pausar.

**Notas**:
- gh CLI exigiu `git branch --set-upstream-to` após push via URL-com-token (o push HTTPS+gh-token não seta tracking automaticamente). Workaround documentado para futuras sessões.
- Sem CI no repo (`statusCheckRollup: []`); merge depende apenas de `mergeable: CLEAN`.
- Backfill foi mais rápido que o orçado porque pydantic v2 + `model_validate_json` é trivial e o volume é pequeno (400 linhas total).

---

### Sessão 1 — 2026-05-20 (PLANEJAMENTO)

**Duração estimada**: 3-4 horas (sessão longa de planejamento).
**Dia do sprint**: 0 (pré-execução).

**Atividade**:
- Análise dos resultados do mine de produção do dia anterior (PR #19, 400 pares produzidos).
- Discussão estratégica das 5 estratégias possíveis para expandir o dataset.
- Lançamento de 2 agentes de pesquisa: (a) LoRA data sizing (Opus, completo), (b) brainstorm de fontes de dado real (Opus, completo).
- Síntese dos relatórios em decisões concretas.
- Iteração sobre os 5 caminhos (perguntas detalhadas sobre cada um).
- Refinamento do plano em 3 iterações com Gustavo.
- Identificação dos 2 gaps no plano inicial: sourcing limpo (D5) e contradição R2.
- Decisão de adapter shrinking SÓ para R2 (D2). R5 wait-and-see (D3).
- Plano final declarado: 3 semanas, 5 smells mantidos, sem LLM hybrid, source tagging desde dia 1.
- Criação deste documento (PROGRESSO) e do `PLANO-SPRINT-MINERACAO.md`.

**Resultado**:
- 2 documentos criados em `reports/`:
  - `PLANO-SPRINT-MINERACAO.md` — plano completo com contexto, decisões, execução detalhada por dia, riscos, critérios de pronto, referências.
  - `PROGRESSO-SPRINT-MINERACAO.md` (este) — tracker live + log de sessões + snapshots.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 1 do sprint** começa amanhã (ou na próxima sessão). Detalhe completo em `PLANO-SPRINT-MINERACAO.md §4 Semana 1 Dia 1`. Resumo: branch `feature/source-tagging`, adiciona campo `source` no schema, cria `data/test/`, backfill dos 400 pares existentes, testes, PR, merge.
- Em paralelo no Dia 2: enviar email aos autores do ActRef pedindo replication package.

**Notas**:
- O plano assume implementação ágil com IA assistindo. Custo realista do Caminho 5 (rename-aware) estimado em 5-8 dias focados, não 15+.
- Gates de validação (precision em amostra cross-file, behavioral check) são críticos pra confiar no Caminho 5 — não pular.
- Checkpoint do dia 14 é o ponto onde a estratégia R5 vai ser concretizada. Não improvisar antes desse checkpoint.
- Caminho 1 (LLM hybrid) está descartado **provisoriamente** — pode voltar se Caminho A (adapter shrink) falhar no smoke training do Dia 17.

---

## 🧭 Mapa rápido — onde estão as coisas

| Coisa | Onde |
|---|---|
| Plano completo | `reports/PLANO-SPRINT-MINERACAO.md` |
| Estado atual | aqui (este arquivo, §🎯) |
| Próxima ação | aqui (este arquivo, §🎯 → "Próxima ação concreta") |
| Decisões do plano | `reports/PLANO-SPRINT-MINERACAO.md §3` |
| Decisões durante sprint | aqui (§🗂️) |
| Resultado mine pré-sprint | `reports/2026-05-20-mine-resultado.md` |
| Engine de mineração | `extracao/mineracao/minerador.py` |
| Runner de produção | `extracao/execucao/mineracao.py` |
| Schema | `core/schema.py` |
| Curador (revisão dupla) | `extracao/execucao/filtro_smells.py` |
| Treino LoRA | `trilha_b/training/` |
| Testes | `tests/` |
| Logs de execuções anteriores | `logs/` |
