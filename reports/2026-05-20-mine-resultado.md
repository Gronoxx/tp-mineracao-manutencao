# Mine de produção — resultado (2026-05-20)

Corrida overnight da configuração de produção entregue na PR #19.

## Configuração da corrida

- **Repositórios:** 36 maduros (16 originais + 20 expandidos pelo Plano 3).
- **Janela:** 2020-01-01 → 2024-12-31.
- **Cap por smell** (calibrado pelo "max útil" do agente de literatura LoRA):
  `{R1: 4000, R2: 3500, R3: 1500, R4: 2500, R5: 2000}`.
- **Verificação:** estrita + permissiva (E1, `partial_threshold = 0.1`).
- **Duração:** 42,8 minutos (muito mais rápido que a estimativa inicial de 6–24h).
- **Falhas:** 1 repo (`hypothesis`) não clonou por falta de `git-lfs` no ambiente — os outros 35 mineraram sem erro.
- **Log da corrida:** `logs/mine-2026-05-19-2145.log`.

## Resultado: 400 pares totais (258 estritos + 142 parciais)

| smell | total | estrito | parcial | min viável (agente) | recomendado | % do mínimo |
|---|---:|---:|---:|---:|---:|---:|
| **R3** Named Constant | **129** | 73 | 56 | 200 | 500 | **64%** |
| **R4** Guard Clauses | **127** | 95 | 32 | 400 | 800 | **32%** |
| **R2** Parameter Object | **53** | 26 | 27 | 600 | 1.200 | **9%** |
| **R5** Remove Dead Code | **50** | 47 | 3 | 300 | 600 | **17%** |
| **R1** Extract Method | **41** | 17 | 24 | 800 | 1.500 | **5%** |
| **TOTAL** | **400** | **258** | **142** | | | |

**Todos os 5 smells ficaram abaixo do piso mínimo viável** apontado pela literatura.
R3 é o menos longe (64% do mínimo); R1 é o pior (5%).

## Contribuição do E1 (verificação permissiva)

Sem o E1 da PR #18 (estrita apenas):
- R1: 17 (em vez de 41) — **E1 mais do que dobrou o R1.**
- R2: 26 (em vez de 53) — **E1 dobrou o R2.**
- R3: 73 / R4: 95 / R5: 47 — contribuições parciais menores.

Mais da metade dos R1 (24/41) e quase metade dos R2 (27/53) vêm de pares parciais — esses pedem mais cuidado na curadoria humana (PR #13, revisão dupla).

## Detalhamento — top 5 repos por smell

### R1 — Extract Method (41 pares)
| repo | pares |
|---|---:|
| scipy | 5 |
| ansible | 5 |
| spaCy | 4 |
| pandas | 3 |
| mypy | 3 |

### R2 — Introduce Parameter Object (53 pares)
| repo | pares |
|---|---:|
| pandas | 13 |
| scikit-learn | 6 |
| transformers | 6 |
| mypy | 4 |
| spaCy | 4 |

### R3 — Named Constant (129 pares)
| repo | pares |
|---|---:|
| transformers | 20 |
| numpy | 19 |
| sympy | 15 |
| matplotlib | 14 |
| spaCy | 13 |

### R4 — Guard Clauses (127 pares)
| repo | pares |
|---|---:|
| sympy | 17 |
| ansible | 16 |
| transformers | 14 |
| pandas | 10 |
| networkx | 8 |

### R5 — Remove Dead Code (50 pares)
| repo | pares |
|---|---:|
| numpy | 11 |
| matplotlib | 11 |
| statsmodels | 6 |
| sympy | 5 |
| networkx | 5 |

## Observações

1. **A expansão de repos (PR #19) valeu a pena.** Vários top contribuidores são novos (transformers, scipy, spaCy, ansible, matplotlib, networkx, sympy via originais mas com peso menor). Os 16 originais sozinhos teriam gerado significativamente menos.

2. **Distribuição saudável de proveniência.** Nenhum repo único domina mais de ~25% de um smell; o top-5 sempre cobre a maioria mas com pluralidade.

3. **R5 quase só estrito** (47/50 estritos) — o detector `dead_code` AST (PR #16) é conservador e raramente concorda com "ainda dispara, mas menos".

4. **R3 mais perto da meta.** Refator mais mecânico (literal numérico → constante nomeada) → mais frequente em commits explícitos de refactor + maior taxa de aceitação do detector.

5. **Encruzilhada estratégica.** Os smells com **menos dado real** (R1, R2) são também (a) os **mais difíceis de gerar sinteticamente** sem perda de realismo (extract method e parameter object exigem decisões estruturais) e (b) os **mais arriscados de tratar com adapter encolhido** (são tarefas estruturalmente mais complexas, precisam de capacidade do modelo).

## Próximos passos

Decisão estratégica em aberto. Agente em curso para mapear todas as vias plausíveis de **mais dado real** para R1/R2 (datasets etiquetados existentes, mineração via PRs marcados no GitHub, RefactoringMiner / SWE-Refactor, etc.) antes de comprometer com augmentação sintética.

Histórico relevante das decisões já tomadas:
- PRs de auditoria (#8–#17): bugs corrigidos, pipeline robusto.
- PR #18: E1 (verificação permissiva) — +46% no smoke.
- PR #19: produção pronta (36 repos, cap calibrado).
- Decisão pendente após o relatório do agente: dataset complementar (caminho a definir) vs aceitar o yield atual com calibração de adapter.
