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
- **Dia do sprint**: 8 ✓ (entrou na Semana 2; Dia 9 em fila)
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

**Dia 9 do sprint** — C5c.4 behavioral validation amostrada:

1. Branch `feature/c5c4-behavioral-validation`.
2. Função `_behavioral_check(fn1_source, fn2_source) -> bool`: usa `hypothesis` para gerar 10 inputs sintéticos, executa ambas, compara outputs.
3. Aplicação em amostra de 50 pares cross-file, mede taxa de aprovação.
4. Calibração: aprovação > 70% → pipeline confiável; < 50% → ajustar thresholds.
5. PR + merge.

(Detalhes em `PLANO-SPRINT-MINERACAO.md §4 Semana 2 Dia 9`.)

### Branch / PR ativo

(nenhum — Dia 8 mesclado via PR #28)

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
| 2026-05-20 | Modo overnight/auto declarado para a Semana 1 inteira | Gustavo indisponível por horas; janela ociosa custosa | Avançou Dia 1→7 em 1 sessão sem pausas |
| 2026-05-20 | Dia 2: `OracleEntry` em vez de `RefactoringPair` para catalog | PyRef CSV não tem código (só commit URL+tipo); `RefactoringPair` exige before/after | Catálogo metadata-only versionado em `data/test/`; extração de código fica para Dia 3+ |
| 2026-05-20 | `.gitignore` muda de `data/` para `data/**` + exceções `!data/test/**` | Git não re-inclui filhos quando pai está ignorado | Permite versionar oracles sem deixar `data/raw/` vazar |
| 2026-05-20 | Dia 3: `mine_specific_commits` BYPASSA o filtro de keyword | Commits PyRef já são refatorações validadas; keyword é pré-filtro de recall, perderia commits validados | +25 pares `adjacent_oracle` em 44s (3 repos) |
| 2026-05-20 | Dia 4: `mine_pr` resolve PR→SHA fora do escopo do minerador | Mantém minerador puro/offline-testável; caller (Dia 10-11) usa `gh pr view` | Composição clean; mine_pr = wrapper sobre mine_specific_commits |
| 2026-05-20 | Dia 5: file rename é detectado por padrão (PyDriller+git) | Investigação revelou que comportamento já existia; só faltava cobertura | Dia 5 vira regressão + documentação em vez de implementação |
| 2026-05-20 | Dia 6-7: AST similarity ignora nomes de identificadores | Robusto a rename de variáveis; sensível só a estrutura | `identifier_overlap` complementar fica para Dia 8 (combater FP em estruturas genéricas) |
| 2026-05-20 | Calibração formal do `cross_file_threshold` deferida para Dia 12 | Mass mine #2 produzirá o universo de calibração; 50 pares oracle ainda não têm código extraído | Threshold 0.4-0.7 documentado empiricamente nos testes |
| 2026-05-20 | Smoke em flask/click/requests deferido para Dia 12 | Custo de rede alto overnight; testes unitários cobrem correção | Mass mine #2 já cobre yield delta em modo combinado |

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

### Snapshot Fim Semana 1 (Dia 7) — 2026-05-20

**Toda a Semana 1 executada em uma única sessão overnight (~5h).**

#### Yield em `data/raw/` por smell × source

| Smell | mined_commit | adjacent_oracle | mined_pr | cross_file | Total | Min viável | % do min |
|---|---:|---:|---:|---:|---:|---:|---:|
| R1 Extract Method | 41 | 1 | 0 | 0 | 42 | 800 | 5% |
| R2 Parameter Object | 53 | 7 | 0 | 0 | 60 | 600 (140 c/ r=8) | 10% (43%) |
| R3 Named Constant | 129 | 12 | 0 | 0 | 141 | 200 | 70% |
| R4 Guard Clauses | 127 | 4 | 0 | 0 | 131 | 400 | 33% |
| R5 Remove Dead Code | 50 | 1 | 0 | 0 | 51 | 300 | 17% |
| **Total** | **400** | **25** | **0** | **0** | **425** | | |

Pares `mined_pr` e `cross_file` permanecem em 0 — a infraestrutura está pronta mas a execução ainda não foi disparada (será no mass mine #2 do Dia 12).

#### Yield em `data/test/` (oracles, held-out)

- `oracle_pyref_test.jsonl`: **573 entradas** (451 TP, 114 FP, 8 CTP). **25 R1+TP** (material primário de teste R1).
- `oracle_sourcery_test.jsonl`: 10 entradas (catálogo bibliográfico).

#### PRs mesclados na semana

| PR | Dia | Escopo | Suite após |
|---:|---|---|---:|
| #22 | 1 | Schema `source` field + backfill 400 pares | 143 |
| #23 | 2 | OracleEntry + catálogo PyRef+Sourcery | 155 |
| #24 | 3 | `mine_specific_commits` + adjacent mining | 161 |
| #25 | 4 | `mine_pr` + `require_keyword` flag | 168 |
| #26 | 5 | Rename-aware regression tests | 171 |
| #27 | 6-7 | AST similarity cross-file (APTED) | 192 |

#### Caminhos disponíveis no minerador (fim Sem 1)

| Função | Filtro keyword | Source tag default | Caso de uso |
|---|---|---|---|
| `mine(repo, out)` | obrigatório | `mined_commit` | mineração cega per-file |
| `mine(repo, out, require_keyword=False)` | desligado | `mined_commit` | janela curta sem keyword |
| `mine(repo, out, cross_file_threshold=0.7)` | obrigatório | `mined_commit` | + cross-file matching |
| `mine_specific_commits(repo, out, hashes)` | bypassado | `adjacent_oracle` | commits de oracle |
| `mine_pr(repo, out, merge_shas)` | bypassado | `mined_pr` | merge commits de PR |

#### Threshold calibrado (parcial)

- **AST similarity**: 0.7 sugerido pelo plano, **0.4 empírico** no fixture de teste (dead code removal). Calibração formal deferida ao Dia 12 (mass mine #2 vai produzir o universo necessário).
- **Shape distance**: 0.5 default no pré-filtro. Não revisado empiricamente — sera junto com Dia 12.
- **Partial threshold (E1)**: 0.1 default em `mine_specific_commits` e `mine_pr`. Inalterado em `mine()` (None = estrito).

#### Decisões durante a semana

(Já em §🗂️ abaixo.)

#### Próxima ação

Dia 8 — C5c.3 identifier overlap mitigation. Combate FP em cross-file matching adicionando filtro Jaccard sobre nomes de identificadores livres + funções chamadas.

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

### Sessão 8 — 2026-05-20 (Dia 8 — C5c.3 identifier overlap mitigation)

**Duração estimada**: ~20 min.
**Dia do sprint**: 8 de 21 (início Semana 2).
**Modo**: overnight / auto-mode.

**Atividade**:
- `extracao/mineracao/ast_similarity.py`: adicionados `_identifiers_of()` e `identifier_overlap(src1, src2)`. Set de `ast.Name` + `ast.Attribute.attr` por função, Jaccard sobre os sets.
- `find_cross_file_candidates` ganha `identifier_overlap_threshold` (default 0.0). Quando > 0, rejeita pares com Jaccard abaixo do threshold APÓS o filtro AST similarity.
- `mine()` ganha `identifier_overlap_threshold`. Propagação via `_cross_file_pairs_for_commit`.
- `tests/test_identifier_overlap.py`: 10 testes (5x identifier_overlap puro, 3x find_cross_file_candidates, 2x mine() smoke). Cenário-alvo validado: `_validate_input` HTTP vs DB → AST sim=1.0, identifier_overlap=0.0 → rejeitado com threshold 0.5.
- PR #28 criado, mesclado via squash (commit `1214030`).

**Resultado**:
- ✓ Pipeline cross-file agora tem 2 filtros: AST similarity (forma) + identifier Jaccard (vocabulário). Combate FP "duas formas iguais em domínios diferentes".
- ✓ `pytest tests/ -q` → **202 passing** (192 + 10).
- ✓ Default 0.0 preserva comportamento — flag opt-in.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 9** — C5c.4 behavioral validation amostrada (hypothesis lib).

**Notas**:
- Decisão: `_identifiers_of` NÃO inclui o nome do FunctionDef em si (parser não vê `FunctionDef.name` como `ast.Name`). Para FPs onde só o nome bate (`_validate_input` em ambos), a interseção fica baseada nos identificadores DENTRO do corpo — semanticamente correto.
- Tradeoff: o Jaccard ignora a frequência (uma palavra usada 10× conta igual a uma usada 1×). Para refatorações que mantêm vocabulário mas redistribuem uso, o overlap continua alto — comportamento desejável.
- Calibração formal do threshold (0.5 sugerido) fica para Dia 12 mass mine #2.

---

### Sessão 7 — 2026-05-20 (Dias 6-7 — C5c.2 AST similarity cross-file) + Snapshot Semana 1

**Duração estimada**: ~60 min.
**Dia do sprint**: 6-7 de 21 (Semana 1 fechada).
**Modo**: overnight / auto-mode.

**Atividade**:
- Instalação `apted 1.0.3` (puro Python, sem build C — `pip install` direto).
- `extracao/mineracao/ast_similarity.py` (NEW, ~190 linhas):
  - `ShapeHash` dataclass (n_stmts/n_params/depth/n_returns).
  - `shape_hash(src)` e `shape_distance(a, b)` — pré-filtro O(n) por forma.
  - `_ast_to_apted_tree(node)` — bracket-notation usando só tipos de nó AST (ignora nomes de identificadores; robusto a rename de variáveis).
  - `ast_similarity(src1, src2) -> float | None` — APTED edit distance normalizado por nº total de nós.
  - `find_cross_file_candidates(before_files, after_files, shape_threshold=0.5, similarity_threshold=0.7)` — pareia funções gone/fresh entre arquivos diferentes; best-per-gone matching.
- `extracao/mineracao/minerador.py`:
  - `mine()` ganha `cross_file_threshold: float | None = None` (opt-in).
  - `_cross_file_pairs_for_commit()` — adapter dos dicts do find_cross_file_candidates para o formato consumido por `verify_pair`.
- `tests/test_ast_similarity.py`: 17 testes unitários (shape, similaridade, find_cross_file).
- `tests/test_minerador_cross_file.py`: 4 testes end-to-end (default off, ativação captura par, threshold apertado, ids únicos). Fixture: dead code removal cross-file (foo migra utils.py → models.py com 3 dead vars removidas — similaridade ~0.45).
- Calibração inicial do threshold: 0.4 empírico no fixture; 0.7 sugerido pelo plano. Calibração formal deferida para o Dia 12.
- PR #27 criado, mesclado via squash (commit `f859eec`).
- **Snapshot Semana 1 escrito em §📊** — yield breakdown, PRs mesclados, caminhos disponíveis, decisões consolidadas.

**Resultado**:
- ✓ 3 caminhos do minerador agora disponíveis: per-file (default), cross-file (opt-in), commit-list (mine_specific_commits) — todos com source tagging.
- ✓ `pytest tests/ -q` → **192 passing** (171 + 21).
- ✓ Contribuição publicável independente (D5 do plano): "primeiro miner Python open-source com extração rename-aware + cross-file".
- ✓ **Semana 1 do sprint completa em 1 sessão overnight**.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 8** (Semana 2) — C5c.3 identifier overlap mitigation (Jaccard sobre nomes livres + chamadas, combate FP em estruturas genéricas).

**Notas**:
- AST similarity tem limites conhecidos: Parameter Object cross-file tem similaridade ~0.17 (mudança drástica de assinatura+corpo) — threshold realista NÃO captura. Para esses, o caminho continua per-file. Documentado no PR.
- Extract Method cross-file tem `helper_sources=[]` no adapter — Dia 6-7 não cobre helpers que cruzam arquivos. Suficiente para o sprint; caso real será visto no mass mine #2.
- Decisão de design: usar `apted` puro Python em vez de variantes C — instalação trivial em qualquer ambiente, latência aceitável para tamanhos típicos (~150 nós).

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
