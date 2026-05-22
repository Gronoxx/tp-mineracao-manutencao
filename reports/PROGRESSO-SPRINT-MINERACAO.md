# Progresso do Sprint de Mineração

**Período**: 2026-05-20 a 2026-06-10 (21 dias).
**Plano completo**: `reports/PLANO-SPRINT-MINERACAO.md` (ler em conjunto com este).

---

## 🚧 Antes de retomar: ver `reports/GATES-PENDENTES.md`

Documento criado na Sessão 11 (pós-overnight) listando todos os gates de
qualidade pendentes com decisões padrão para o Dia 11. **G0 já executado**
(quality check passou com 0 FAILs nos 25 adjacent_oracle).

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

- **Data da última atualização**: 2026-05-22 (Sessão 13 — Dia 12 ✓, esgotamento dos curados)
- **Dia do sprint**: 12 ✓ — esgotamento massivo dos 36 repos curados (Fases A+B+D). Cross-file (Fase C) abortada.
- **Semana**: 2
- **Fase**: Execução — esgotamento dos curados COMPLETO. Próximo: análise (Dia 13) + checkpoint R5 (Dia 14) + C4 Java translation (Dia 15-16) para fechar R1.

### Yield atual por smell

Pós-Dia 12 (Fases A+B+D): **432 → 4.400 pares** (10,2×). Detalhes em `reports/SESSAO-MINERACAO-MASSIVA-2026-05.md`.

| Smell | Início (Dia 11) | **Final (Dia 12)** | Min viável | % do min | Status |
|---|---:|---:|---:|---:|---|
| R1 Extract Method | 44 | **439** | 800 | 55% | aguarda C4 (Dia 15-16) |
| R2 Parameter Object | 61 | **619** | 600 (140 c/ r=8) | **103%** | ✓ |
| R3 Named Constant | 143 | **1.376** | 200 | 688% | ✓✓✓ |
| R4 Guard Clauses | 133 | **1.294** | 400 | 324% | ✓ |
| R5 Remove Dead Code | 51 | **672** | 300 | 224% | ✓ |
| **Total** | **432** | **4.400** | | | |

Por source: mined_commit=4.375, adjacent_oracle=22, mined_pr=3, cross_file=0.

**4 de 5 smells passaram o mínimo viável.** Apenas R1 pendente (será fechado por C4).

### Próxima ação concreta

**Dia 13 — Análise + fixes** (ver `reports/SESSAO-MINERACAO-MASSIVA-2026-05.md §7):

1. **Fix de cache de clones** nos runners (`exhaust_curated_mine.py`, `c5_first_years_mine.py`): adicionar `clone_repo_to` para evitar re-clone (Issue #5 — Fase D levou 23h por re-clonar tudo).
2. **Retry numpy/Pillow** first-years (falharam no clone — Issue #5).
3. **Análise estatística completa** do dataset + relatório de yield (`reports/2026-XX-XX-mine-pos-c5.md` do plano §4 Dia 13).
4. **Investigação cross-file** dedicada (threshold <0.5, multi-commit) — timeboxed (Issue #3).
5. **G4 holístico otimizado** (paralelizar APTED ou cachear AST parse).

### Branch / PR ativo

`feature/exhaust-curated-runner` — PR com 3 scripts da Sessão 13: `exhaust_curated_mine.py`, `c5_first_years_mine.py`, `calibrate_cross_file.py`. (PR #33 do c2_mass_mine_pr.py já mesclado no Dia 11.)

### Pendências para retomar com supervisão

> 🚧 **LEIA PRIMEIRO**: `reports/GATES-PENDENTES.md` — lista completa de gates
> de qualidade com decisões padrão para o Dia 11.

1. **Mass query PR search**: `python3 extracao/execucao/pr_search.py` (18 shards = 6 labels × 3 anos).
2. **Dia 11**: integração do cache com `mine_pr` + quality check automático.
3. **Dia 12 (mass mine #2)**: modo COMBINADO conservador (commit + PR + adjacent), cross-file DESLIGADO até calibração.
4. **Dia 13**: análise de yield + quality check (G4) como gate.
5. **Dia 14**: checkpoint R5 (decisão sobre adapter).
6. **Email ActRef**: ação humana pendente do Gustavo desde Dia 2.
7. **Calibração threshold cross-file (G1+G2)**: roda em mass mine SEPARADO (não no #2), após o #2 estabilizar.
8. **Smoke G3 (`require_keyword=False`)**: rodar em flask/click/requests antes de ativar no mass mine.

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
| 2026-05-20 | Dia 11: cap qualitativo (36 repos curados) em vez de numérico no c2 mass mine | Mass search retornou 1.457 repos / 12.148 PRs; rodar tudo = 100s GB + horas; user pediu "maduros e confiáveis" | Reduziu a 7 repos / 201 PRs (interseção curados ∩ pr_list); yield 7 pares 100% CLEAN |
| 2026-05-20 | Dia 11: estratégia de esgotamento dos 36 curados antes de tier-2 | Maximizar uso dos repos já validados; tier-2 (home-assistant 2.905 PRs etc.) entra depois | Fases A→B→C com decisão informada por yield real |
| 2026-05-20 | G3 smoke rodado e PRECISION validada via G4 | Decisão de `require_keyword=False` no mass mine #2 estava pendente; G3 mediu delta ~19x e G4 mediu FAIL rate 5-9% | Habilita Fase B do esgotamento como opção informada; mantém kw=True como default até decisão de Dia 12 |
| 2026-05-21 | Dia 12: ativar `require_keyword=False` na Fase B em escala | G3 (Dia 11) confirmou FAIL rate só 5-9%; risco aceitável | +1.976 pares (maior salto da sessão) |
| 2026-05-21 | Fase C (cross-file) ABORTADA após 10h | Yield ZERO em todos thresholds, mesmo em repos grandes; detector exige same-commit + similaridade ≥0.5, refator real é multi-commit + sim ~0.3 | Cross-file deferido p/ investigação dedicada Dia 13; contribuição "miner cross-file" existe no código mas yield prático=0 |
| 2026-05-21 | Dia 12: minerar primeiros 7 anos de cada repo (Fase D) | Premissa do grupo: refator (esp. R1) mais comum no início do projeto | +1.314 pares; premissa confirmada (celery/matplotlib/django renderam dezenas) |
| 2026-05-22 | Aceitar G4 amostral estratificado em vez de holístico | G4 full em 4.400 pares leva 3h+ (APTED O(n²)); amostra de 500 (100/smell) dá estimativa rápida | Gate validado a 88% CLEAN, 2% FAIL sem custo de horas |

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

### Snapshot Fim Semana 2 (Dia 12 — pós esgotamento dos curados)

**Sessão 13 (autônoma, ~25h wall-clock) executou Fases A+B+D. Fase C abortada.**

#### Yield em `data/raw/` por smell × source

| Smell | mined_commit | adjacent_oracle | mined_pr | cross_file | Total | Min viável | % do min |
|---|---:|---:|---:|---:|---:|---:|---:|
| R1 Extract Method | 437 | 1 | 1 | 0 | 439 | 800 | 55% |
| R2 Parameter Object | 615 | 3 | 1 | 0 | 619 | 600 | 103% |
| R3 Named Constant | 1.366 | 9 | 1 | 0 | 1.376 | 200 | 688% |
| R4 Guard Clauses | 1.287 | 7 | 0 | 0 | 1.294 | 400 | 324% |
| R5 Remove Dead Code | 670 | 2 | 0 | 0 | 672 | 300 | 224% |
| **Total** | **4.375** | **22** | **3** | **0** | **4.400** | | |

(adjacent_oracle caiu 25→22 e mined_pr caiu 7→3 por idempotência — pares
sobrescritos por mined_commit, conteúdo preservado. Issue #4.)

#### Contribuição por fase

| Fase | Estratégia | Yield | Tempo |
|---|---|---:|---|
| A | Expansão temporal 2015-2019, kw=True | +678 | 80 min |
| B | kw=False mass mine 2020-2024 | +1.976 | 132 min |
| C | Cross-file (calibração + mineração) | 0 (ABORTADA) | 10h |
| D | First-7-years, 26 repos, kw=False | +1.314 | 23h |

#### Quality check (gate G4)

Amostra estratificada (500 pares, 100/smell): **88,2% CLEAN, 9,8% WARN, 2,0% FAIL.**

#### Checkpoint R5 (antecipado do Dia 14)

R5 = 672 pares ≥ 300 → **mantém adapter cheio (r=16 full, 18,46M params)**. ✓
Decisão do checkpoint crítico resolvida com folga.

#### Documento para o grupo

`reports/SESSAO-MINERACAO-MASSIVA-2026-05.md` — explicação completa da sessão,
cada script, resultados, problemas. Autocontido.

#### Repos e janela

38 repos únicos (35 curados + 3 PyRef). Criados 2009-2019 (idade média 13a).
Janela: 2015-2024 (Fases A/B) + primeiros anos pré-2015 de 26 repos (Fase D).

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

### Sessão 13 — 2026-05-20 a 2026-05-22 (Dia 12 — esgotamento massivo dos curados)

**Duração estimada**: ~25h wall-clock (maioria background; ~10h queimados na Fase C abortada).
**Dia do sprint**: 12 de 21.
**Modo**: AUTO declarado pelo Gustavo (rodar fases sequencialmente, registrar issues, resolver sozinho).

**Atividade**:
- Estratégia de esgotamento dos 36 repos curados em 4 fases (A→B→C→D).
- `scripts/exhaust_curated_mine.py` (NEW): runner parametrizável (since/to/require_keyword/cross_file_threshold via CLI) reusando `REPOS` de `mineracao.py`.
- **Fase A** — expansão temporal 2015-2019, kw=True: +678 pares (80 min).
- **Fase B** — kw=False mass mine 2020-2024: +1.976 pares (132 min). Maior salto.
- `scripts/calibrate_cross_file.py` (NEW): calibração G1+G2 do cross_file_threshold.
- **Fase C** — cross-file: ABORTADA após 10h (0 pares em todos thresholds, mesmo repos grandes). Issue #3.
- `scripts/c5_first_years_mine.py` (NEW): minera primeiros 7 anos de cada repo (truncado em 2014-12-31).
- **Fase D** — first-7-years, 26 repos (12 pulados por criados ≥2015), kw=False: +1.314 pares (23h por re-clone — Issue #5). numpy/Pillow falharam.
- G4 amostral estratificado após Fases B e D: ~88% CLEAN, ~2% FAIL.
- `logs/auto_session_issues.md` (NEW): 5 issues documentados.
- `reports/SESSAO-MINERACAO-MASSIVA-2026-05.md` (NEW): documento explicativo para o grupo.

**Resultado**:
- ✓ Dataset **432 → 4.400 pares (10,2×)**.
- ✓ **4 de 5 smells acima do mínimo viável** (R2=103%, R3=688%, R4=324%, R5=224%). R1=55% (aguarda C4).
- ✓ Checkpoint R5 antecipado resolvido: 672 ≥ 300 → adapter cheio mantido.
- ✓ G4 amostral validou qualidade (88% CLEAN, 2% FAIL).
- ✓ 3 scripts novos + documento de grupo + 5 issues registrados.

**Bloqueadores**:
- numpy/Pillow first-years perdidos (clone falhou — disco/re-clone). Retry no Dia 13.

**Próxima ação**:
- **Dia 13**: fix de cache de clones nos runners, retry numpy/Pillow, análise estatística, investigação cross-file dedicada.

**Notas**:
- 2 erros custaram tempo: Fase C (10h sem retorno — cross-file rende 0 em produção) e Fase D (23h vs ~2h por re-clone). Ambos com root cause documentado e fix planejado.
- Decisão de cap qualitativo (36 curados, não os 1.457 do pr_search) veio do Gustavo no Dia 11 e guiou toda a sessão.
- Premissa do grupo (refator nos primeiros anos) confirmada empiricamente na Fase D.

---

### Sessão 12 — 2026-05-20 (Dia 11 — C2 mass PR search + integração mine_pr + G3 + G4)

**Duração estimada**: ~2h (incluindo background tasks).
**Dia do sprint**: 11 de 21.
**Modo**: ACORDADO + verificando (gates explícitos, sem auto-mode).

**Atividade**:
- Sanity check: 219 passing, main sincronizada.
- **Mass PR search** (`extracao/execucao/pr_search.py`): 18 shards (6 labels × 3 anos) em ~15 min. Resultado: **12.148 PRs em 1.457 repos** (cache em `data/pr_list.json`, gitignored). Distribuição heavy-tailed (home-assistant=2.905, top 5 repos=33% do volume, 1.141 repos com 1-5 PRs cada).
- **Decisão de cap** (consultada com Gustavo): em vez de cap numérico, usar análise qualitativa — manter apenas os 36 repos curados em `mineracao.py:REPOS`. Cross-reference revelou: 7 dos 36 curados aparecem no pr_list (201 PRs); 29 curados NÃO usam labels de refactor consistentemente (django, flask, numpy, etc.).
- `scripts/c2_mass_mine_pr.py` (NEW): espelha `c3_adjacent_mining.py`. Lê `data/pr_list.json`, agrupa por repo, dispara `mine_pr(repo_url, output_path, merge_commit_shas=[...])` em cada repo com clones cached em `/tmp/c2_pr_clones/`. CLI: `--input`, `--out`, `--clones-dir`, `--partial-threshold`, `--limit-repos`.
- Subset curado gerado: `data/pr_list_curated.json` (201 PRs, 7 repos).
- **Smoke c2** (`--limit-repos 2`, httpx+fastapi): 0 pares — diagnóstico: PRs labelados nesses repos são micro-changes (drop import, type annotation, lazy module load) que não disparam R1-R5. Pipeline funciona; yield baixo por design dos labels.
- **Full c2 curado** (7 repos, 201 PRs, 21.5 min): **+7 pares mined_pr** (pandas=5, scrapy=2; httpx/fastapi/pydantic/Pillow/scikit-learn=0). Best yield/PR: pandas 14.7%.
- **G4 quality check em mined_pr**: **7/7 CLEAN (100%), 0 FAILs, 0 WARNs**.
- **G4 holistic em `data/raw/`**: 432 pares, 366 CLEAN (84.7%), 51 WARN (11.8%), 15 FAIL (3.5%). FAILs/WARNs são do mined_commit pré-existente; mined_pr 100% limpo.
- **G3 smoke** (flask/click/requests, kw=True vs False):
  - flask: 2 → 23 (delta 11.5x). G4 nos kw=False: 2 FAILs (8.7%).
  - click: 1 → 9 (delta 9x). G4: 0 FAILs.
  - requests: 0 → 25 (delta ∞). G4: 2 FAILs (8%).
  - **Total: 3 → 57 (delta ~19x médio). FAIL rate 5-9%**. Zona "10-100x" exige decisão informada (não automático).

**Resultado**:
- ✓ Infraestrutura C2 (PR mining) validada end-to-end: pr_search.py (mass) + c2_mass_mine_pr.py (integração) + mine_pr (Dia 4) + G4 (quality check).
- ✓ +7 pares mined_pr em `data/raw/`, 100% CLEAN. Total: 432 pares (was 425).
- ✓ G3 + G4 precision-validados para `require_keyword=False`. Habilita Fase B do esgotamento como opção informada.
- ✓ Estratégia de esgotamento dos 36 curados delineada (Fases A→B→C).
- ✓ `pytest tests/ -q` mantém 219 passing.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 12 — Fase A**: expandir janela temporal (SINCE 2020→2015) e re-rodar mass mine nos 36 curados com kw=True. Yield esperado: +100-300 pares.
- Após Fase A: decidir Fase B (kw=False mass mine, ~19x alavanca, custo ~6-12h overnight) vs Fase C-calibração (G1+G2 cross-file).

**Notas**:
- A descoberta principal não é o yield (+7) e sim o mapa do universo: 12.148 PRs em 1.457 repos é universo enorme; só 7 dos 36 curados (~19%) usam labels refactor. Os 29 curados sem labels precisam de caminhos alternativos (commit-mode kw=False, adjacent_oracle expandido, cross-file).
- Pandas e scrapy mostraram-se os melhores rendedores em modo PR (14.7% e 2.9% yield/PR). Confirma intuição de que repos maduros com PRs longos e disciplinados rendem melhor.
- Decisão de não ativar `require_keyword=False` agora foi precautória (zona 10-100x exige análise); resultado de G4 (5-9% FAIL) sugere que ativar é mais SEGURO do que se temia. Será decidido no Dia 12 após Fase A.
- gh CLI workaround do push HTTPS+token segue obrigatório.

---

### Sessão 10 — 2026-05-20 (Dia 10 — C2 PR search via GraphQL) + Fechamento overnight

**Duração estimada**: ~30 min.
**Dia do sprint**: 10 de 21 — **fim da sessão overnight**.
**Modo**: overnight / auto-mode.

**Atividade**:
- `extracao/execucao/pr_search.py` (NEW): script com `_gh_graphql()` wrapper, `search_label_year(label, year)` paginado, `merge_cache()` dedup por `(repo, pr_number)`, `load/save_cache`. CLI completo (`--labels`, `--years`, `--limit-shards`, `--output`).
- Auth via `gh api graphql` (token gh já autenticado, scope `repo`) — sem PAT custom.
- `tests/test_pr_search.py`: 10 testes 100% offline (mock de `_gh_graphql` via `unittest.mock.patch`).
- **Smoke real**: `--labels tech-debt --years 2024 --limit-shards 1` → **41 PRs reais** em ~3s. Distribuição: top repo `SSC-ICT-Innovatie/nl-kat-coordination` (19), `AnimalFoodBank/afb-requests` (9), `chevah/compat` (3), etc.
- PR #30 criado, mesclado via squash (commit `7e631bd`).
- **Decisão de parada**: Dia 11+ requer mass query GraphQL (rate limits, 18 shards × paginação imprevisível) e mass mine #2 (várias horas) — ambos com risco operacional alto overnight sem supervisão. Critério #1 do plano de overnight ("Dia 7 + snapshot") foi alcançado e ultrapassado em 3 dias.

**Resultado**:
- ✓ Infraestrutura completa para mass PR mining: `pr_search.py` + `mine_pr()` (Dia 4) + integração via `data/pr_list.json`.
- ✓ Smoke real validou API GitHub + parsing + cache.
- ✓ `pytest tests/ -q` → **219 passing** (209 + 10).
- ✓ **10 dos 21 dias do sprint completos em uma única sessão overnight (~5h)**.

**Bloqueadores**:
- Nenhum — parada por escolha (network-bound futuro com supervisão).

**Próxima ação**:
- **Dia 11 (com supervisão)**: rodar `pr_search.py` mass + integrar com `mine_pr()`.

**Notas finais da sessão**:
- O sprint avançou em ritmo muito acima do previsto: 10 dias em 1 sessão vs. plano de 1 dia por sessão. Razões: (a) ferramentas pré-existentes já eram boa base (PyDriller, pydantic), (b) muitos dias eram refinamentos pequenos (Dia 5 era só regressão; Dia 9 era um módulo isolado), (c) modo auto-mode evitou pausas para confirmação.
- Decisões importantes documentadas no §🗂️.
- Suite cresceu 140 → 219 (+79 testes em 10 dias).
- 9 PRs técnicos mesclados (#22-#30), 10 commits de PROGRESSO direto na main.

---

### Sessão 9 — 2026-05-20 (Dia 9 — C5c.4 behavioral validation amostrada)

**Duração estimada**: ~25 min.
**Dia do sprint**: 9 de 21.
**Modo**: overnight / auto-mode.

**Atividade**:
- `pip install hypothesis` (6.152.9).
- `extracao/mineracao/behavioral_check.py` (NEW): utilitário **offline** para comparar pares por amostragem de entradas.
  - `_compile_function(src)` compila FunctionDef top-level em callable (namespace mínimo).
  - `_with_timeout(fn, args, secs)` hard timeout via SIGALRM (UNIX).
  - `behavioral_check(src_before, src_after, n_samples=10, timeout=0.5s)` usa `hypothesis @given` programático com estratégia `one_of(int, str, list, None)`. Compara outputs ou tipos de exceção. Retorna `BehavioralCheckResult` dataclass.
- Design: **NUNCA usar em `mine()`** — risco de side effects de código arbitrário. Apenas validação offline.
- `tests/test_behavioral_check.py`: 7 testes (identicas, divergentes, dead code, sem params, exceção, código inválido, dataclass).
- PR #29 criado, mesclado via squash (commit `e9a3c32`).

**Resultado**:
- ✓ Módulo `behavioral_check` pronto para calibração formal.
- ✓ `pytest tests/ -q` → **209 passing** (202 + 7).
- ✓ Estratégia de input simples mas robusta: cobre função pura típica; funções com tipos complexos fica `inconclusive`.

**Bloqueadores**:
- Nenhum.

**Próxima ação**:
- **Dia 10** — C2 PR search via GraphQL.

**Notas**:
- Decisão: usar `hypothesis @given` programático em vez de gerador custom — alinha com o plano e dá mais cobertura (shrinking + generation strategies prontas). Custo: 1 dep adicional.
- Sandbox tem `__builtins__` padrão — código com `os.system` etc. ainda roda. Para repos remotos isso seria perigoso; mitigação atual é "só usar offline pós-mineração". Sandbox mais restrito (sem `__builtins__`) impediria quase tudo.
- Calibração formal (50 pares cross-file) fica para Dia 12 mass mine #2 — universo necessário virá de lá.

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
