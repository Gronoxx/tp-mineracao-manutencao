# Decisões e Contexto do Projeto — Dataset de Refatoração Python + LoRA

**Última atualização:** 2026-05-27 (decisões de modelo/oracle/split + julgamento R3 em curso — ver §0)  
**Projeto:** TP de Engenharia de Software II — UFMG  
**Repositórios:** tp-mineracao-manutencao · tp-es2-dataset · tp-es2-anotador

---

## 0. Atualizações recentes (2026-05-27/28)

### 2026-05-28 — Estratégia para os smells abaixo do piso (R2, R3, R4): mineração ancorada em rule-ID de linter

Descoberta (agentes Opus + verificação por commit-search no GitHub): **minerar commits que corrigem uma regra objetiva de linter** (ruff/pylint), ancorando no **rule-ID**, contorna a subjetividade que matava a mineração cega (yield 1–4%). O rule-ID é o sinal objetivo de intenção que faltava — e **reforça a tese** (yield ∝ objetividade do critério; aqui a regra do linter É a objetividade).

| Smell | Regra (ruff/pylint) | Filtro de diff (restaura objetividade) | Volume bruto | Pares projetados |
|---|---|---|---|---|
| R2 | `PLR0913`/`R0913` too-many-arguments | função perde ≥2 params **e** surge `@dataclass`/`NamedTuple`/`TypedDict`/attrs/pydantic usado como tipo do novo param | ~557 (53 alta-precisão c/ token "dataclass extract") | ~45–70 |
| R3 | `PLR2004`/`R2004` magic-value-comparison | literal → constante ALL_CAPS nomeada; rejeita supressões `# noqa` | ~1.513 (587 c/ "constant") | ~40–100 |
| R4 | `PLR1702`/`R1702` too-many-nested-blocks | profundidade cai + surge early-return/guard | a medir no piloto | a medir |

**Pipeline (nativo, sem clonar):** commit-search por rule-ID (API REST) → diff dos `.py` via API → `extract_candidates`+`verify_pair` (mesmos detectores do projeto) → juiz Gemma → filtro estrutural. **Oracle-clean:** ruff/pylint ≠ PyRef/Sourcery, e o Sourcery não aplica Introduce Parameter Object em Python. Excluir commits de bot e repos do test set (70–100). Ressalvas: regras ruff são pós-2022 (skew temporal 2023–26); recall do R2 enviesado pró-`dataclass`.

**Reservas** (se o nativo não bastar): R2 via RefactoringMiner "Merge Parameter" (Java→tradução); R4 via commit mining das codebases maduras mapeadas (mitmproxy, localstack, keras, manim, rich…). Datasets curados (MaRV, dkdal) são **bust** para R2/R3 (baseados em RefactoringMiner, que não rotula esses tipos).

**Resultado (2026-05-28 — batch de 5,5h, 672 candidatos julgados, 180 REAL):** R2 **30/39 REAL (77%)**, R3 **74/382 (19%)**, R4 **13/112 (12%)**; bônus R1 51/120 (42%), R5 12/19 (63%). **Novos totais Tier A REAL: R2 23→53, R3 17→91, R4 52→65** — os três **cruzam o piso de 42** (30% Tier A); R1→135 (+98 Tier B), R5→272. Os yields são **5–25× os da mineração cega** (R3 1,2%→19%, R2 3%→77%) — confirma e fortalece a RQ (o rule-ID supre a objetividade que faltava; vira contribuição metodológica). **Destrava o Tier C:** com a base real ≥42, R2/R3/R4 podem ser preenchidos com sintético até 140 sem furar a regra de 30%. Pendências: revisão humana (como todo Tier A) + proveniência (pares vêm de ~782 repos pequenos/obscuros → expansão ruff-sobre-os-36-maduros recupera qualidade). Minerador: `smoke_c4/repo/pilot_rule_id_mining.py` (provenance `rule_id_mined`).

Rule-IDs para os 5 smells (agente Opus, 2026-05-28): R1 add `PLR0915`+`C901`; R5 add `F841`(+`W0101` unreachable). Recall-gap: commit-search por menção acha só <5–10% dos fixes reais e **0% dos 36 repos** foram visitados → expansão recomendada: **ruff-as-diff-detector** sobre os 36 (regra viola no pai, some no filho **E** detector AST confirma), recall 5–15× p/ R1/R5, oracle-safe.

---

Decisões da sessão 2026-05-25→27 (detalhe em `CHECKPOINT_PROJETO.html` + `CHECKPOINT_APENDICE_LIMIARES.html`):

- **Alvo de treino trocado:** Qwen2.5-Coder-1.5B → **Stable Code Instruct 3B** (StabilityAI). Motivo: o alvo era da mesma família do gerador Tier B (Qwen-7B) → risco de auto-destilação. Já aplicado em `trilha_b/training/lora_config.py` (target_modules da arquitetura StableLM são os mesmos Llama-style; verificar template/runtime). Fallback: deepseek-coder-1.3b-instruct.
- **Oracle em dois papéis:** **PyRef = validador determinístico** (pass/fail, ground truth); **Sourcery-AI = comparador/baseline** (o LoRA tem que igualar/superar). Regra: não gerar treino com PyRef nem Sourcery.
- **Split por repositório:** `DataCurator.split()` migrado de `StratifiedShuffleSplit` para `GroupShuffleSplit` (com asserts anti-leakage). Held-out de teste = repos **70–100** em maturidade (mesma métrica dos 36 originais); 40–70 como buffer; **congelar a lista antes de avaliar**.
- **CodeBLEU descartado** (penaliza refatoração correta-mas-diferente). Métricas: smell-resolution (primária) + preservação de comportamento (`eval_execution.py`) + não-introdução de novo smell + human eval. (Não havia código de CodeBLEU a remover.)
- **Tier C:** padrão acadêmico (juiz≠gerador≠alvo; sinal AST objetivo, não a prosa do Gemma; ground truth humano) + **checagem cross-family** com **Mistral 7B Instruct v0.3** (DeepSeek-R1-Distill-7B rejeitado por ser Qwen-based).
- **R3:** backlog **concluído** (2026-05-27): 1.376/1.376 julgados, **17 REAL (1,2%)** — o menor yield dos 5, confirma a RQ com n grande (antes era só o piloto de 51). 17 < piso de 40; complemento (Tier C / aceitar como finding) a decidir. Tier A REAL total: 420 → **436**.
- **R2:** abaixo do piso real (23 < 42 pela regra de 30% Tier A). Alavanca em estudo: baixar o limiar do detector de `>5` (= default do Pylint) para `>4` (catálogos dizem "mais de 3-4"; tradeoff: fica mais estrito que o Pylint).
- **PR mining dos "giants": testado e ABANDONADO (piloto empírico, 2026-05-27).** Entre os 4, só o home-assistant tinha sinal (`code-quality` = 23.186 PRs; airflow/sentry/ray sem label de refac usável — sentry só usa "Tech Debt" em issues). **Piloto:** 500 PRs `code-quality` atômicos (≤3 arquivos) minerados pelo pipeline canônico (`mine_pr`) → **só 3 candidatos (R1×2, R4×1), todos APARENTE → 0 REAL** (taxa de disparo do detector: 0,6%, em ~32 min). Causa: o `code-quality` do home-assistant é dedup de constantes via import (a constante já é nomeada → não dispara R3), remoção de classes/componentes deprecados (≠ dead-code de função/R5), traduções e typing — quase nada casa com os 5 detectores em nível de função. **Conclusão: PR-label mining não é fonte viável para estes smells** (consistente com os +7 do keyword mining). Infra do piloto: `smoke_c4/repo/pilot_ha_codequality.py` + venv `.pilot_venv` (PyDriller; `gh` ausente, usei API REST direta).

---

## 1. Objetivo

Construir um dataset de pares before→after de refatoração Python para 5 code smells e treinar um adaptador LoRA no Qwen2.5-Coder-1.5B. O paper tem **dupla contribuição**: dataset + modelo.

**5 code smells:**
- R1 — Long Method → Extract Method
- R2 — Long Parameter List → Introduce Parameter Object
- R3 — Magic Numbers → Named Constants
- R4 — Deep Nesting → Guard Clauses
- R5 — Dead Code → Remove

**Avaliação held-out (100% independente):** **PyRef = validador determinístico** (pass/fail) + **Sourcery-AI = comparador/baseline** (ver §0); repositórios disjuntos do treino.

---

## 2. Arquitetura do Dataset — Três Tiers

### Tier A — Real Mined (base do dataset)

Commits reais do GitHub minerados via PyDriller por palavras-chave. Pipeline:

```
Commits brutos (PyDriller, keyword mining)
        ↓
Filtro de diff-atomic (a implementar): ≤2 arquivos, diff ≤50L
        ↓
Juiz LLM: Gemma-4-26B-Q3 (REAL / APARENTE + justificativa)
        ↓
Validador estático: detector do smell por AST/lizard
        ↓
Revisão humana 100% — CEGA ao label do Gemma
```

**Regra crítica:** Tier A deve representar ≥30–40% do total de pares de treino.

### Tier B — C4 Translation (só R1)

98 pares gerados por tradução do dataset SWE-Refactor (Java) para Python via Qwen2.5-Coder-7B. Pipeline:

```
SWE-Refactor (350 pares Java, Extract Method)
        ↓
Qwen2.5-Coder-7B: tradução Java→Python
        ↓
Filtro estático (NLOC > 30 OU CC > 10 via lizard): 47 pares
        ↓
LLM judge Gemma (before ≥10L): 51 pares adicionais
        ↓
Total: 98 pares R1 (source: "translated_java")
```

**Separação de modelos Tier B:**
- Gerador: Qwen2.5-Coder-7B (tradução Java→Python, tarefa diferente do alvo)
- Juiz: Gemma-4-26B-Q3
- Alvo de treino: Qwen2.5-Coder-1.5B

Ressalva: gerador (7B) e alvo (1.5B) são da mesma família Qwen — mas a tarefa do 7B é tradução Java→Python, não refatoração Python, portanto não é auto-destilação da tarefa alvo. Documentar nas ameaças à validade.

### Tier C — Fixed Synthetic

Usa os pares APARENTE (before real + after ruim do commit) como semente para gerar afters limpos e cirúrgicos.

```
Par APARENTE: before real (smell confirmado) + after do commit (rejeitado)
        ↓
Verificação AST: before dispara detector estático do smell?
        ↓  (descarta se não)
Extração de sinal estrutural via AST:
  n_params, n_lines, nesting_depth, n_statements
  (NÃO a prosa do Gemma — evita circularidade gerador-juiz)
        ↓
Gerador (llama3.1:8b): prompt com before + sinal AST + regra:
  "Corrija SOMENTE [smell_name], sem introduzir nenhuma outra mudança"
        ↓
Validador estático: after resolve o smell completamente?
        ↓
Juiz Gemma: valida o par gerado (vê código novo, independente)
        ↓
Revisão humana 100% — CEGA ao label do Gemma
```

**Por que Tier C é mais cirúrgico que Tier A:** commits reais são ruidosos por natureza (o desenvolvedor tinha múltiplos objetivos). Aqui o gerador tem um único objetivo explícito, guiado pelo que NÃO fazer (sinal estrutural do before). O resultado tende a ser um par mais focado.

**Ressalva para o paper:** o after não reflete como um desenvolvedor humano específico escreveria — reflete o estilo do llama3.1:8b verificado por humano. Documentar como ameaça de representatividade (validade externa), não de corretude.

---

## 3. Separação de Modelos — Anti-circularidade

| Papel | Modelo | Justificativa |
|---|---|---|
| Juiz (Tier A, B e C) | Gemma-4-26B-Q3 | Avalia, nunca gera |
| Gerador Tier B | Qwen2.5-Coder-7B | Tradução Java→Python |
| Gerador Tier C | llama3.1:8b | ≠ Gemma, ≠ família Qwen-Coder |
| Alvo de treino | **Stable Code Instruct 3B** | StabilityAI — distinto do juiz e de todos os geradores (trocado 2026-05-27, ver §0) |

**Circularidade residual reconhecida:** o sinal estrutural AST no prompt do Tier C foi escolhido especificamente para NÃO usar a prosa do Gemma (que definiria os critérios de geração e validação simultaneamente). O AST não carrega o "raciocínio" do Gemma — carrega propriedades objetivas do código real. Esta escolha precisa ser explicitada e justificada no paper.

---

## 4. Protocolo de Revisão Humana

**Regra absoluta:** revisão humana de 100% de todos os pares em todos os tiers. Inegociável.

**Protocolo cego:** o revisor recebe apenas `(before, after, smell_type + critério)` — **sem o label REAL/APARENTE do Gemma**. Evita annotation bias (o revisor não é influenciado pela decisão do LLM).

**Inter-annotator Agreement (IAA):**
- ≥50 pares revisados em duplo-cego independente
- Distribuídos: ~20 Tier A + ~15 Tier B + ~15 Tier C
- Meta: Cohen's κ ≥ 0.61 (Landis & Koch "substantial")
- κ por tier revela se Tier C é mais ambíguo de avaliar — dado metodológico útil
- κ abaixo do threshold: revisar critério de avaliação e re-treinar revisores

O κ é reportado no paper como evidência de validade do juiz LLM (concordância Gemma vs. humano).

---

## 5. Estado Atual da Coleta (2026-05-24)

| Smell | Tier A avaliados | REAL | Yield | Tier B | Tier C | Status |
|---|---|---|---|---|---|---|
| R1 | 439/439 | 84 | 19% | 98 | — | ✓ Completo |
| R2 | 619/619 | 23 | 3% | — | — | ✓ Completo |
| R3 | 1376/1376 | 17 | 1,2% | — | (Tier C?) | ✓ Completo (2026-05-27) |
| R4 | 1294/1294 | 52 | 4% | — | — | ✓ Completo |
| R5 | 672/672 | 260 | 38% | — | — | ✓ Completo |
| **Total** | **4400 avaliados** | **436 REAL** | **9,9%** | **98 (R1)** | — | **Tier A 100% julgado** |

**Nota R5:** pilot (60%) superestimou o yield real (38%) — os primeiros 50 pares eram uma amostra favorável. Ainda assim 260 pares é o maior volume individual do dataset.

**Decisão sobre R3 (atualizado 2026-05-27):** batch completo julgado — **17 REAL em 1.376 (1,2%)**. Continua abaixo do piso de 40 do test set, mas o yield agora é robusto (não mais piloto) e é o menor dos 5, reforçando a RQ. Complemento a decidir (Tier C a partir dos APARENTE, ou aceitar como smell constrangido junto com R2).

**Modelos disponíveis localmente (Ollama):**
- `batiai/gemma4-26b:q3` — 13GB, juiz principal (~30s/par)
- `qwen2.5-coder:7b-instruct-q4_K_M` — 4.7GB, gerador Tier B
- `llama3.1:8b` — 4.9GB, **gerador Tier C** (3.4 tok/s limpo, cabe inteiro na VRAM)
- `phi4:14b` — 9.1GB, alternativa Tier C (1.3 tok/s)
- `deepseek-coder-v2:16b` — 8.9GB, alternativa Tier C (1.8 tok/s)
- `qwen2.5-coder:1.5b` — alvo de treino

---

## 6. Achado Principal — Yield vs. Objetividade do Critério

> **Este é potencialmente o achado mais forte do paper**, independente dos resultados do LoRA.

### Hipótese emergente

A objetividade do critério do smell prediz o yield de commits puros em mineração por keyword.

### Dados observados (pilot de 50 pares por smell)

| Smell | Yield (batch completo) | Objetividade do critério |
|---|---|---|
| R5 — Dead Code | **38%** | Binária: código morto some ou não |
| R1 — Long Method | **19%** | Semi-objetiva: NLOC tem threshold numérico |
| R4 — Deep Nesting | **4%** | Moderada: nesting é estrutural mas contextual |
| R2 — Long Parameter List | **3%** | Subjetiva: "longa" é julgamento semântico |
| R3 — Magic Numbers | **1,2%** (n=1.376) | Subjetiva: "mágico" é dependente do domínio |

**Nota:** pilot de R5 (60%) superestimou o yield real (38%) — amostra inicial não representativa. O padrão qualitativo se mantém.

**Correlação observada:** Spearman monotônico decrescente entre yield e subjetividade do critério (5/5 pontos na ordem esperada). Calcular ρ formal com métrica quantificada de objetividade.

### Por que isso é publicável

Com cinco pontos de dados e correlação clara (Spearman monotônico decrescente de yield com subjetividade), esta observação sustenta uma RQ própria:

> **RQ-X:** A objetividade do critério de definição de um code smell prediz o yield de refatorações puras em commits minerados por keyword?

Implicação prática: mineração por keyword é uma estratégia válida para smells com critério binário/estrutural (Dead Code, Long Method), mas inadequada como fonte primária para smells com critério semântico/contextual (Magic Numbers, Long Parameter List). Para esses, são necessárias estratégias alternativas (Tier C, mineração dirigida por ferramenta, curadoria manual).

### Como fortalecer o achado

1. **Quantificar a "objetividade"** com uma métrica formal — ex: número de condições binárias verificáveis no critério do smell, ou Cohen's κ entre avaliadores humanos na definição
2. **Replicar em outra linguagem** — se o padrão se mantém em Java (usando o SWE-Refactor dataset), o achado é mais generalizável
3. **Caracterizar os APARENTE por smell** — a taxonomia de "por que foi rejeitado" deve ser feita separadamente para cada smell, revelando se o ruído tem natureza diferente por tipo

### TODO (atualizar com valores finais)

- [x] Substituir yields do pilot pelos yields do batch completo para R4 e R5
- [ ] Calcular correlação de Spearman formal entre yield e objetividade
- [ ] Definir métrica formal de "objetividade do critério"

---

## 7. Decisão Pós-Pilot — Thresholds

O pilot de 50 pares por smell (R3, R4, R5) determina se o batch completo é viável:

| Smell | Fila total | REAL mínimo em 50 | Yield mínimo | Pares esperados no batch |
|---|---|---|---|---|
| R3 | 1376 | 2/50 | ≥4% | ~55 |
| R4 | 1294 | 2/50 | ≥4% | ~52 |
| R5 | 672 | 4/50 | ≥8% | ~54 |

**Decisão:**
- ≥3 smells acima → batch completo + MSR Data Showcase como alvo primário
- 1–2 smells acima → batch só nos que valem + reframe para R1 em profundidade
- 0 smells acima → pivot para análise de yields como achado negativo publicável

---

## 7. Avaliação do LoRA

### Pipeline de métricas (em ordem de aplicação)

```
after gerado pelo LoRA
        ↓
ast.parse(after) → INVÁLIDO: descarta (conta como falha)
        ↓ VÁLIDO
detector(after) → smell ainda presente: falha
        ↓ smell resolvido
CodeBLEU vs. after do oracle (se disponível)
        ↓
human eval em amostra de 30–50 pares
```

### Métricas por ordem de importância para o paper

1. **Smell-resolution rate** — métrica primária. Fração dos afters gerados onde o detector confirma que o smell foi resolvido. Objetivo, independente de LLM.
2. **Parse rate** — pré-requisito. Fração sintaticamente válida.
3. **CodeBLEU vs. oracle** — complementar. Atenção: penaliza refatorações corretas mas estruturalmente diferentes das do oracle. Vai nas ameaças à validade explicitamente.
4. **Human eval** — qualitativo. Amostra de 30–50 pares gerados avaliados por revisores.

### Baselines obrigatórios

- **Zero-shot Qwen2.5-Coder-7B** no mesmo test set (sem fine-tuning) — baseline principal
- **Zero-shot Qwen2.5-Coder-1.5B** no mesmo test set (modelo base sem LoRA) — mostra ganho do fine-tuning

**Nota:** Sourcery é validador no oracle (confirma smell no before), não baseline de geração.

### Ablação de proveniência

Treinar e avaliar LoRA em três configurações:
- Configuração A: Tier A + B apenas
- Configuração B: Tier A + B + C
- Métrica no held-out real nos dois casos

O resultado transforma "origem dos dados" de ameaça filosófica em resultado empírico.

---

## 8. Caracterização dos APARENTE (achado publicável)

Os 81% APARENTE do R1 não são apenas ruído — são um achado sobre a qualidade da mineração por keyword. Plano de análise:

**Amostra:** 100 pares APARENTE do R1 (já disponíveis em `anotacoes_gemma.json`)

**Taxonomia:**
| Categoria | Descrição | Como identificar |
|---|---|---|
| Multi-objetivo | Commit refatorou + adicionou feature/bugfix | Diff com linhas novas não relacionadas |
| Parcial | Extract Method incompleto — função principal ainda longa | Detector dispara no after |
| Mudança de assinatura | Adicionou/removeu parâmetros | AST diff na assinatura |
| Reorganização sem extração | Moveu código sem criar helper real | Nenhuma função nova no after |
| Falso positivo keyword | Mensagem menciona "extract" mas não é refatoração | Diff mínimo ou unrelated |

Esta análise transforma o yield de 19% de número solto em achado com substância: *"X% dos commits com keyword Extract Method são multi-objetivo, Y% são parciais..."*

---

## 9. Requisitos para Publicação

### Target primário: MSR Data Showcase

| Requisito | Status | Ação |
|---|---|---|
| Split treino/teste por repositório | ⚠️ Pendente (D-DEV-08) | Corrigir `DataCurator.split()` para GroupShuffleSplit |
| IAA (κ ≥ 0.61) em ≥50 pares duplo-cego | ⏳ Pendente | Implementar após revisão humana |
| ≥2 baselines para o LoRA | ⏳ Pendente | Zero-shot 7B e 1.5B base |
| Replication package com DOI (Zenodo) | ⏳ Pendente | Criar durante redação do paper |
| Revisão humana protocolo cego | ⏳ Pendente | Implementar no anotador |
| Caracterização dos APARENTE | ⏳ Pendente | Análise manual de 100 pares R1 |
| Ablação de proveniência (A+B vs A+B+C) | ⏳ Pendente | Após coleta completa |
| FAIR compliance (Findable, Accessible…) | ⏳ Pendente | Zenodo + licença aberta |

### Ameaças à validade a documentar (obrigatórias)

1. **Validade de construção:** definição de "refatoração pura" operacionalizada pelo Gemma pode divergir de Fowler/Opdyke — κ Gemma vs. humano é a evidência de alinhamento
2. **Validade interna — circularidade residual Tier C:** sinal AST (não prosa do Gemma) no prompt do gerador mitiga mas não elimina o acoplamento gerador-juiz
3. **Validade externa — representatividade Tier C:** afters sintéticos refletem estilo do llama3.1:8b, não de desenvolvedores humanos reais
4. **Viés de seleção do before no Tier C:** amostra condicionada a commits que misturaram mudanças — pode ter correlação com características do smell
5. **Auto-destilação parcial Tier B:** gerador (Qwen-7B) e alvo (Qwen-1.5B) são da mesma família
6. **CodeBLEU subestima o LoRA:** refatorações corretas mas estruturalmente diferentes das do oracle são penalizadas
7. **Contaminação de pré-treino:** o LLM base (Qwen) pode ter visto código dos repositórios de teste durante pré-treino — impossível de mitigar completamente, mas separação por repo é documentada

---

## 10. Próximos Passos (em ordem de prioridade)

1. **[Em andamento]** Pilot 50 pares R3/R4/R5 → decisão de batch completo
2. **[Blocker]** Corrigir split por repositório (`DataCurator.split()` → GroupShuffleSplit)
3. Implementar protocolo cego no anotador (tp-es2-anotador)
4. Implementar script Tier C (`smoke_tier_c/generate_tier_c.py`) com llama3.1:8b
5. Caracterização manual de 100 pares APARENTE do R1 (taxonomia)
6. Revisão humana de todos os pares (Tier A + B + C) com IAA
7. Treinar LoRA com ablação de proveniência
8. Avaliar no oracle held-out com métricas definidas
9. Criar replication package no Zenodo

---

## 11. Hardware e Modelos

**Máquina:** GTX 1660 SUPER (6GB VRAM) · 15GB RAM · 11GB swap · Ollama 0.20.4

| Modelo | Tamanho | Velocidade | Papel |
|---|---|---|---|
| batiai/gemma4-26b:q3 | 13GB | ~30s/par | Juiz universal |
| qwen2.5-coder:7b-instruct-q4_K_M | 4.7GB | ~20 tok/s | Gerador Tier B |
| llama3.1:8b | 4.9GB | 3.4 tok/s | **Gerador Tier C** |
| qwen2.5-coder:1.5b | 1GB | — | Alvo de treino |
| phi4:14b | 9.1GB | 1.3 tok/s | Reserva Tier C |
| deepseek-coder-v2:16b | 8.9GB | 1.8 tok/s | Reserva Tier C |

**Nota de capacidade Tier C:** llama3.1:8b a 3.4 tok/s + ~300 tokens/par = ~90s/par. Para 1000 pares: ~25h. Viável rodando overnight.
