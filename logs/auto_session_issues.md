# Auto Session Issues Log

**Sessão**: 13 (Dia 12 do sprint — automode).
**Início**: 2026-05-20.

Registro de problemas não-críticos encontrados durante a execução autônoma das Fases A→B→C. Cada entrada: contexto, decisão tomada, justificativa.

---

## Issue #5 — Fase D: 23h de duração + numpy/Pillow falharam (re-clone wasteful + disco cheio)

**Quando**: Fase D (2026-05-21 18:25 → 2026-05-22 ~17:35, 1389 min = 23h).

**Root cause (2 problemas)**:

1. **Re-clone a cada execução**: `c5_first_years_mine.py` e
   `exhaust_curated_mine.py` NÃO passam `clone_repo_to`. PyDriller clona
   cada repo num temp dir novo (`/var/folders/.../T/tmpXXX/`) por invocação,
   sem reaproveitar. Cada uma das Fases A/B/D re-clonou os 26-36 repos do
   zero. (Os scripts c2/c3 do Dia 11/Dia 3 cacheiam; estes não herdaram.)

2. **numpy + Pillow falharam no git clone** (exit 128). Causa provável:
   disco a 88% (24GB livres) insuficiente para clones grandes em temp
   (numpy ~1GB, várias cópias temp simultâneas de fases anteriores não
   limpas). numpy consumiu 7.4h tentando antes de falhar.

**Severidade**: Média. Custou tempo (23h vs ~2h ideal). 24/26 repos
mineraram OK. numpy/Pillow first-years (~50-100 pares estimados) perdidos.

**Decisão**:
- NÃO retry numpy/Pillow agora (custaria horas). Premissa first-years já
  validada por 24 repos (+1.314 pares).
- Limpar temp clones para liberar disco.
- **Melhoria deferida (Dia 13)**: adicionar `clone_repo_to=/tmp/mine_clones`
  nos runners exhaust/c5 para cachear clones (como c2/c3 já fazem). Reduz
  re-clone de horas para minutos.
- Retry numpy/Pillow first-years após o fix de cache (Dia 13).

---

## Issue #4 — Fase B: 4 pares mined_pr foram sobrescritos por mined_commit (idempotência por id)

**Quando**: Pós Fase B (2026-05-21, ~14:12).

**Diagnóstico**: pré-Fase B `data/raw/` tinha 7 pares `source="mined_pr"`
(pandas=5, scrapy=2). Pós-Fase B: 3 pares mined_pr remaining.

**Causa**: Fase B rodou `mine()` com kw=False na mesma janela 2020-2024 dos
mined_pr. O merge dentro de `_merge_write` é idempotente por `id` (gerado
de `repo+commit+file+function`). Quando o mesmo (repo, commit, file, func)
foi encontrado por mine() E por mine_pr() (Dia 11), o último escritor
ganha — sobrescreveu source="mined_pr" com source="mined_commit".

**Severidade**: Cosmética. Os PARES continuam no dataset — só perderam a
tag específica `mined_pr` para `mined_commit`. Conteúdo idêntico, treino
não é afetado. Apenas analytics de proveniência fica menos preciso.

**Decisão**: aceitar. Documentar comportamento de idempotência. Para
preservar provenância exclusiva no futuro, mine() poderia checar se o id
já existe com source != atual e fundir tags (ex.: "mined_commit+mined_pr").
Fica como melhoria future deferred.

---

## Issue #3 — Fase C ABORTADA: cross-file pipeline rende ZERO em produção

**Quando**: Fase C-1 v2 (2026-05-21, killed às 11:58 após 10h de execução).

**Diagnóstico final** após v2 (3 thresholds completados: 0.5, 0.6, 0.7 em
numpy/pandas/sympy/scipy/matplotlib): **0 cross_file pairs em TODAS as
configurações testadas**.

**Hipótese**: cross-file matching no estado atual não captura nada porque:
1. AST similarity 0.5+ é alta demais — refator cross-file típico (movimentação
   + nome novo + assinatura ajustada) tem similaridade EMPÍRICA ~0.3-0.4
   (alinhado com o fixture do teste C5c.2 na Sessão 7).
2. PyDriller só pareia gone+fresh no MESMO commit — refators frequentemente
   ocorrem em múltiplos commits.

**Severidade**: ALTA pelo custo de oportunidade. C-1 v2 consumiu 10h sem
gerar pares utilizáveis. Inviável continuar este caminho na sessão atual.

**Decisão**:
- ABORTAR Fase C-1 + Fase C-2 nesta sessão.
- Manter `cross_file_threshold=None` (desligado) na Fase B e além.
- Documentar como deferred work para Dia 13-14 com investigação dedicada
  (testar thresholds < 0.5, considerar multi-commit pairing, validar contra
  ground truth se possível).

**Impacto no sprint**: contribuição publicável "primeiro miner Python
open-source com cross-file" continua existindo no código (infrastructure
done, tests pass), mas o YIELD prático é zero por enquanto. Não bloqueia
metas de dataset (R3 já ✓, R4 quase, R5 ok, R2 com adapter shrink). R1
seguirá dependendo do Caminho 4 (C4 Java translation Dia 15-16).

---

## Issue #2 — Fase C-1: zero cross-file pairs nos 3 repos pequenos

**Quando**: Fase C-1 (2026-05-21, ~01:20).

**Diagnóstico**: rodei `mine()` com `cross_file_threshold` em {0.5..0.9} nos 3
repos pequenos (flask/click/requests) janela 2020-2024. Yield: 0 cross_file
pairs em TODOS os thresholds.

**Causa raiz**: cross-file matching exige funções GONE em arquivo A + funções
FRESH em arquivo B no MESMO commit. Em repos pequenos com ~6 anos de janela,
refatorações cross-file são raras. Universo de calibração insuficiente.

**Severidade**: Não-crítica. Bloqueia G2 (behavioral_check) mas não impede o
sprint. Calibração falha = manter threshold conservador (0.9 ou desligado).

**Decisão**: ampliar conjunto de calibração para os 5 top yielders da Fase A
(numpy, pandas, sympy, scipy, matplotlib). Estes têm milhares de commits e
funções movendo entre arquivos. Custo: ~75 min adicionais.

**Mitigação alternativa (se nova rodada também falhar)**: usar threshold=0.7
(palpite da literatura citado no plano) na Fase C-2 mass mine, e rodar G2
post-hoc no universo gerado pela própria mass mine.

---

## Issue #1 — Fase A: hypothesis clone falhou

**Quando**: Fase A (2026-05-20 ~18:11), repo 36/36.

**Erro**:
```
FALHA em hypothesis: GitCommandError: Cmd('git') failed due to: exit code(128)
```

**Causa provável**: HypothesisWorks/hypothesis usa git-lfs (já mencionado no
snapshot pré-sprint do PROGRESSO: "hypothesis falhou no clone por falta de
git-lfs"). É o mesmo bug do mass mine #1.

**Severidade**: Não-crítica. 35/36 repos minerados com sucesso. Hypothesis
contribui marginalmente (não estava nos top renderers no mass mine #1).

**Decisão**: aceitar o skip. Adicionar `try/except` específico no runner
seria over-engineering — o `except Exception` no `mineracao.py` já captura
isso e continua. Documentar como limitação conhecida.

**Mitigação futura**: instalar git-lfs no ambiente, ou remover hypothesis
da lista REPOS curada. Deferido para Dia 13+.

---

