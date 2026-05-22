# Sessão de Mineração Massiva — Maio 2026 (Dias 11-12 do Sprint)

> **Documento para o grupo.** Explica o que foi feito na sessão de mineração
> de larga escala que elevou o dataset de **432 → 4.400 pares** de
> refatoração. Lê-se de forma autocontida — não exige contexto prévio do
> sprint.

**Período**: 2026-05-20 a 2026-05-22 (Dias 11-12 do sprint de 21 dias).
**Resultado**: dataset 10,2× maior, 4 de 5 smells acima do mínimo viável.

---

## 1. Contexto: por que minerar mais

O objetivo do sprint é montar um dataset de pares de refatoração
(código *antes* → código *depois*) grande o suficiente para treinar 5
adapters LoRA, um por tipo de refatoração ("smell"):

| Código | Smell | O que é |
|---|---|---|
| R1 | Extract Method | Extrair trecho de função longa para um helper |
| R2 | Parameter Object | Agrupar muitos parâmetros num objeto |
| R3 | Named Constant | Substituir número mágico por constante nomeada |
| R4 | Guard Clauses | Achatar condicionais aninhadas com retorno antecipado |
| R5 | Remove Dead Code | Remover código morto/inalcançável |

Antes desta sessão tínhamos **432 pares** — muito abaixo do mínimo
recomendado pela literatura (800 para R1, 600 para R2, etc.). Esta sessão
executou 4 estratégias de expansão.

---

## 2. Como o minerador funciona (visão geral)

O minerador (`extracao/mineracao/minerador.py`, função `mine()`) varre o
histórico git de um repositório e, para cada commit:

1. **(opcional) Filtro de keyword**: olha a mensagem do commit. Se
   `require_keyword=True` (padrão), só processa commits cuja mensagem
   menciona refator (palavras como "refactor", "extract", "cleanup",
   "simplify"). Se `require_keyword=False`, processa **todos** os commits.
2. **Detecção de smell**: para cada função modificada, roda detectores
   estáticos. Um par é gerado quando o detector dispara no *antes* e
   **não** dispara (ou dispara com magnitude reduzida ≥10%) no *depois* —
   ou seja, a refatoração "consertou" o smell.
3. **Tag de proveniência** (`source`): cada par recebe um rótulo indicando
   de onde veio (`mined_commit`, `mined_pr`, `adjacent_oracle`, etc.).

Cada par produzido é gravado em `data/raw/<smell>.jsonl`. A escrita é
**idempotente**: o merge é por `id` (derivado de repo+commit+arquivo+função),
então rodar o mesmo repo 2× não duplica.

---

## 3. Os scripts usados nesta sessão

Quatro scripts orquestraram a mineração. Todos chamam `mine()` por baixo,
variando os parâmetros.

### 3.1 `scripts/c2_mass_mine_pr.py` — Mineração via PRs do GitHub (Dia 11)

**O que faz**: lê uma lista de Pull Requests rotulados como "refactor"
(produzida por `extracao/execucao/pr_search.py` via GraphQL do GitHub) e,
para cada repo, minera os *merge commits* desses PRs. Os pares recebem
`source="mined_pr"`.

**Premissa**: PRs marcados com labels `refactoring/cleanup/tech-debt` são
refatorações já curadas por humanos.

**Resultado**: a busca massiva encontrou **12.148 PRs em 1.457 repos**. Como
decidimos usar só repositórios maduros e confiáveis (os 36 da lista curada),
filtramos para **7 repos / 201 PRs**. Yield: **+7 pares** (pandas=5, scrapy=2).

**Lição**: yield baixo nos repos curados — a maioria dos PRs rotulados
"refactor" nesses projetos são micro-mudanças (remover import, ajustar type
annotation) que não disparam nossos detectores. Os repos que rotulam PRs de
forma disciplinada (ex.: home-assistant, 2.905 PRs) ficaram de fora por não
estarem na lista curada.

### 3.2 `scripts/exhaust_curated_mine.py` — Runner parametrizável (Fases A e B)

**O que faz**: roda `mine()` nos 36 repos curados, mas com janela temporal,
filtro de keyword e threshold cross-file configuráveis via CLI. Permitiu
rodar fases distintas sem editar o runner de produção.

Usado em duas fases:

#### Fase A — Expansão temporal (janela 2015-2019)
```
python3 scripts/exhaust_curated_mine.py --since 2015-01-01 --to 2019-12-31
```
**Premissa**: o mass mine anterior só cobriu 2020-2024. Os 5 anos
anteriores (2015-2019) eram território não minerado.
**Resultado**: **+678 pares** em 80 min. R3 sozinho ganhou +155.

#### Fase B — Mineração sem filtro de keyword (janela 2020-2024)
```
python3 scripts/exhaust_curated_mine.py --since 2020-01-01 --to 2024-12-31 --no-require-keyword
```
**Premissa**: muitos commits de refatoração não mencionam "refactor" na
mensagem. Desligar o filtro de keyword capta esses casos escondidos.
**Resultado**: **+1.976 pares** em 132 min — o maior salto da sessão.

> Antes de ativar `--no-require-keyword` em escala, rodamos um teste-piloto
> (gate "G3") em flask/click/requests: yield subiu ~19× ao desligar o
> filtro, com taxa de falso-positivo de apenas 5-9% (medida pelo quality
> check). Por isso foi seguro ativar.

### 3.3 `scripts/c5_first_years_mine.py` — Mineração dos primeiros anos (Fase D)

**O que faz**: minera os **primeiros 7 anos** de cada repo, truncando em
2014-12-31 para não re-minerar o que já cobrimos.

**Regra aplicada**:
- Se o repo foi criado em **2015 ou depois**: pular (primeiros 7 anos já
  cobertos pelas Fases A+B). → 12 repos pulados.
- Se foi criado **antes de 2015**: minerar de `created_at` até 2014-12-31.
  → 26 repos minerados.

**Premissa (sugerida pelo grupo)**: refatoração — especialmente de métodos
longos (R1) — é mais comum nos primeiros anos de um projeto, quando o código
cresce rápido e precisa ser reorganizado.

**Resultado**: **+1.314 pares** (R1=121, R2=188, R3=405, R4=321, R5=279).
A premissa se confirmou: repos antigos como celery, matplotlib e django
renderam dezenas de pares cada nos primeiros anos.

**Ressalva**: a fase levou 23h (deveria ser ~2h) porque os runners
re-clonam cada repo do zero a cada execução. numpy e Pillow falharam no
clone (disco cheio) — seus primeiros-anos ficaram de fora (~50-100 pares
perdidos, a recuperar no Dia 13 após corrigir o cache de clones).

### 3.4 `scripts/calibrate_cross_file.py` — Calibração cross-file (Fase C, ABORTADA)

**O que faria**: calibrar o threshold de detecção de refatorações que movem
uma função de um arquivo para outro (cross-file), variando o limiar de
similaridade estrutural (AST) em {0.5, 0.6, 0.7, 0.8, 0.9} e medindo
precisão por equivalência comportamental.

**Resultado**: **abortada após 10h sem produzir pares.** O matching
cross-file rendeu ZERO em todos os thresholds testados, mesmo em repos
grandes. Conclusão: refatorações cross-file reais têm similaridade
estrutural baixa (~0.3) e ocorrem ao longo de múltiplos commits — o detector
atual (que exige funções no mesmo commit, similaridade ≥0.5) não as captura.
Investigação dedicada foi adiada para o Dia 13.

### 3.5 `scripts/quality_check_pairs.py` — Gate de qualidade (usado após cada fase)

**O que faz**: validação estática (sem executar código) que sinaliza
prováveis falsos-positivos. Marca cada par como CLEAN/WARN/FAIL com base em:
- **FAIL**: antes==depois, AST não parseia, ou similaridade AST < 0.10
  (códigos completamente diferentes — pareamento errado).
- **WARN**: similaridade entre 0.10 e 0.30 (mudança drástica), ou funções
  com <3 linhas (trivial demais).

**Resultado** (amostra estratificada de 500 pares, 100 por smell):
**88,2% CLEAN, 9,8% WARN, 2,0% FAIL** — dataset limpo, dentro do critério
(<20% WARN, FAIL baixo).

---

## 4. O dataset resultante

### 4.1 Yield por smell

| Smell | Início | **Final** | Min viável | % do mínimo |
|---|---:|---:|---:|---:|
| R1 Extract Method | 44 | **439** | 800 | 55% |
| R2 Parameter Object | 61 | **619** | 600 | **103%** ✓ |
| R3 Named Constant | 143 | **1.376** | 200 | 688% ✓ |
| R4 Guard Clauses | 133 | **1.294** | 400 | 324% ✓ |
| R5 Remove Dead Code | 51 | **672** | 300 | 224% ✓ |
| **Total** | **432** | **4.400** | | |

R1 (Extract Method) continua o único abaixo do mínimo — será fechado no
Dia 15-16 com tradução de datasets Java→Python (Caminho C4).

### 4.2 Por fonte de mineração

| Fonte (`source`) | Pares | Origem |
|---|---:|---|
| `mined_commit` | 4.375 | Varredura de commits (mass mine #1 + Fases A, B, D) |
| `adjacent_oracle` | 22 | Commits do catálogo PyRef (refator já validado) |
| `mined_pr` | 3 | Merge commits de PRs rotulados "refactor" |
| `cross_file` | 0 | (Fase C abortada) |

### 4.3 Repositórios e janela temporal

- **38 repositórios únicos** (35 da lista curada de "repos maduros" — com
  >5k stars, >5 anos, CI/testes — + 3 do catálogo PyRef).
- **Janela formal varrida**: 2015-2024 (mass mine + Fases A/B) e os
  primeiros anos pré-2015 de 26 repos (Fase D).
- **Idade dos repos**: criados entre 2009 (celery) e 2019 (httpx), idade
  média 13 anos. 63% criados antes de 2014.
- **Distribuição efetiva dos commits**: ~80% de 2020-2024, ~20% de
  2010-2019 (algumas amostras de 2013 via PyRef).

---

## 5. Validação de qualidade

Após cada fase rodamos o quality check estático ("gate G4"):

| Momento | CLEAN | WARN | FAIL |
|---|---:|---:|---:|
| Pós Dia 11 (mined_pr) | 100% | 0% | 0% |
| Pós Fase A (1.078 pares) | 83,4% | 12,2% | 4,4% |
| Pós Fase B (amostra 500) | 88,0% | 10,2% | 1,8% |
| Pós Fase D (amostra 500) | 88,2% | 9,8% | 2,0% |

O dataset está consistentemente acima de 83% CLEAN com FAIL <5%. Os FAILs
são pares onde o pareamento antes/depois ficou estruturalmente muito
distante (detectados automaticamente, podem ser filtrados no treino).

> Nota: o quality check completo nos 4.400 pares leva 3h+ (o cálculo de
> similaridade AST via APTED é O(n²) no tamanho da função). Por isso usamos
> amostragem estratificada (100 pares por smell) para estimativa rápida.

---

## 6. Problemas encontrados e decisões

Todos documentados em `logs/auto_session_issues.md`. Resumo:

| # | Problema | Decisão |
|---|---|---|
| 1 | hypothesis falha no clone (git-lfs) | Aceitar skip; 35/36 repos OK |
| 2 | Cross-file 0 em repos pequenos | Re-rodar com repos grandes |
| 3 | **Cross-file 0 total (Fase C, 10h)** | Abortar; investigação dedicada no Dia 13 |
| 4 | Pares mined_pr sobrescritos por mined_commit | Aceitar (idempotência por id; pares preservados, só muda o rótulo de fonte) |
| 5 | **Fase D 23h + numpy/Pillow falharam** | Root cause: runners re-clonam. Fix de cache + retry no Dia 13 |

---

## 7. Próximos passos (Dia 13+)

1. **Corrigir cache de clones** nos runners (re-clone → cached): reduz horas
   para minutos.
2. **Retry numpy/Pillow** first-years (após o fix).
3. **Investigar cross-file** com critério mais permissivo (threshold <0.5,
   pareamento multi-commit).
4. **Análise estatística completa** do dataset + relatório de yield.
5. **Dia 14**: checkpoint R5 (já passou — 672 pares mantém adapter cheio).
6. **Dia 15-16**: Caminho C4 (tradução Java→Python) para fechar o gap de R1.

---

## 8. Onde estão as coisas

| Coisa | Caminho |
|---|---|
| Scripts de mineração | `scripts/c2_mass_mine_pr.py`, `exhaust_curated_mine.py`, `c5_first_years_mine.py`, `calibrate_cross_file.py` |
| Gate de qualidade | `scripts/quality_check_pairs.py` |
| Engine de mineração | `extracao/mineracao/minerador.py` |
| Lista de repos curados | `extracao/execucao/mineracao.py` (`REPOS`) |
| Dataset final | `data/raw/*.jsonl` (gitignored — local) |
| Logs das fases | `logs/phase_*.log` |
| Log de problemas | `logs/auto_session_issues.md` |
| Progresso do sprint | `reports/PROGRESSO-SPRINT-MINERACAO.md` |
| Gates de qualidade | `reports/GATES-PENDENTES.md` |
