# Decisões durante o Desenvolvimento — Trilha B (Treino e Avaliação dos LoRAs)

Registro de decisões tomadas durante a implementação que não estavam descritas na proposta original (PROPOSTA.html / ESCOPO_E_TRILHAS.html / CATALOGO_SMELLS.html).

---

## D-DEV-01 — Hiperparâmetros LoRA escolhidos autonomamente
**Data:** 12/05/2026
**Contexto:** A proposta define apenas que se usará "Qwen2.5-Coder-1.5B + LoRA" e tarefa P3 prevê "Hyperparameter tuning — variar rank, alpha, lr nos LoRAs; reportar melhor configuração" (sem valores iniciais especificados).
**O que foi implementado:** `training/lora_config.py` define defaults: `rank=16`, `alpha=32` (alpha = 2× rank, regra comum), `dropout=0.05`, `learning_rate=2e-4`, `num_train_epochs=3`, `warmup_ratio=0.03`, `lr_scheduler_type="cosine"`, `weight_decay=0.01`, `max_grad_norm=1.0`, `max_seq_length=2048`, `per_device_train_batch_size=1`, `gradient_accumulation_steps=8` (effective batch=8), `gradient_checkpointing=True`, `fp16=True`. Valores são razoáveis para Qwen2.5-Coder em GPU 8-16GB, mas não justificados na proposta.
**Impacto:** Define o ponto de partida das LoRAs. Se hyperparameter tuning (P3) for executado, esses defaults serão pontos de comparação. Comparabilidade com B0/B1/B3 baselines depende de fixar esses valores entre R1–R5.
**Ação recomendada:** Manter como defaults documentados; agendar varredura quando entrar P3.

---

## D-DEV-02 — Target modules LoRA: todas as 7 projeções (q, k, v, o, gate, up, down)
**Data:** 12/05/2026
**Contexto:** Proposta não especifica quais módulos do Qwen recebem LoRA.
**O que foi implementado:** `LORA_TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]`. Cobre atenção (q,k,v,o) + MLP (gate, up, down) — equivalente ao "all linear" do PEFT. No smoke_test.py, em contraste, são apenas `["q_proj", "v_proj"]` (subset clássico do paper LoRA original).
**Impacto:** "All linear" maximiza expressividade e dobra/triplica número de parâmetros treináveis (~20-30M vs ~5M para q+v). Custo de memória e tempo de treino aumenta. Adapters ficarão maiores (proposta menciona "5-50 MB" — com all linear pode passar de 50 MB para Qwen-1.5B).
**Ação recomendada:** Documentar; em P3 testar contra apenas q+v para medir trade-off tamanho/qualidade.

---

## D-DEV-03 — Detecção automática de quantização 4-bit por memória GPU
**Data:** 12/05/2026
**Contexto:** Proposta diz "treina em 1-3h em GPU gratuita (Colab/Kaggle)" — implica T4 16GB ou similar. Não menciona quantização.
**O que foi implementado:** `lora_config.py` define `GPU_MEMORY_4BIT_THRESHOLD_GB = 8.0`. `load_model_and_tokenizer` ativa BitsAndBytesConfig nf4 + double quant + compute dtype fp16 quando a memória livre < 8 GB. Acima, carrega em fp16 sem quantização.
**Impacto:** Threshold 8 GB é decisão de tooling. Qwen2.5-Coder-1.5B em fp16 ocupa ~3 GB peso + ~2-4 GB ativações com gradient_checkpointing — provavelmente cabe em 8 GB sem 4-bit. Threshold 8 pode ativar 4-bit em casos em que fp16 caberia, degradando qualidade da LoRA sem necessidade.
**Ação recomendada:** Reduzir threshold (ex: 6 GB) ou exigir flag explícita. Documentar trade-off qualidade vs memória.

---

## D-DEV-04 — Prompt template proprietário (`<|system|>`, `<|user|>`, `<|assistant|>`) em vez do chat template oficial do Qwen
**Data:** 12/05/2026
**Contexto:** Proposta não define formato de prompt.
**O que foi implementado:** `training/instruction_templates.py` define um template manual: `<|system|>...\n<|user|>...\n<|assistant|>...`. Qwen2.5-Coder-Instruct tem chat template oficial com tags `<|im_start|>system\n...<|im_end|>` aplicado via `tokenizer.apply_chat_template()`. Usar tags diferentes faz o modelo tokenizar `<|system|>` como tokens de texto comum, não como tokens especiais — o modelo nunca viu esse formato durante pretraining.
**Impacto:** Sub-ótimo. O modelo precisará aprender o novo formato via LoRA antes de aprender a tarefa. Convergência mais lenta, qualidade final pior, e baseline B0 (zero-shot Qwen-Coder) usaria o template oficial — comparação injusta.
**Ação recomendada:** Trocar para `tokenizer.apply_chat_template([{role:"system", content:...}, {role:"user", content:before}, {role:"assistant", content:after}])`. Reverter para alinhamento com B0.

---

## D-DEV-05 — `refactoring_rule` hardcoded em inglês por smell type
**Data:** 12/05/2026
**Contexto:** Proposta especifica os 5 refactorings (R1=Extract Method, R2=Parameter Object, R3=Named Constant, R4=Guard Clauses, R5=Remove Dead Code) mas não dá texto de prompt.
**O que foi implementado:** `instruction_templates.py` define `smell_description` + `refactoring_rule` por smell. Textos detalhados, em inglês, sem versionamento ou ablation. Ex (R3): "Every literal number or string that encodes domain knowledge must be extracted to a module-level constant with a descriptive ALL_CAPS name. The constant name must convey the business meaning, not just the value (e.g. MAX_RETRY_COUNT = 3, not THREE = 3)."
**Impacto:** As regras introduzem viés específico (ALL_CAPS, dataclass __post_init__, guard clauses left-aligned). Se mineração da Trilha A trouxer pares onde o refactoring real não seguiu essas regras (ex: nome em PascalCase, validação fora de __post_init__), há mismatch instrução vs label, prejudicando aprendizado.
**Ação recomendada:** Validar que as regras batem com a maioria dos pares minerados antes de treinar; considerar regras mais soft ou múltiplas variações.

---

## D-DEV-06 — Schema R1–R5 fixo em Pydantic Literal; sem espaço para classes/multi-smell
**Data:** 12/05/2026
**Contexto:** Proposta lista 9 smells detectados e 5 LoRAs de refatoração (R1–R5). Smells multi-função/de classe (Feature Envy, God Class, Shotgun Surgery, Divergent Change) ficaram em Future Work.
**O que foi implementado:** `data/schema.py` define `SmellType = Literal["R1", "R2", "R3", "R4", "R5"]`. Rígido. Adicionar R6/R7 exige mudança de tipo.
**Impacto:** Fechado ao escopo atual — alinhado com a proposta. Sem impacto de validade científica.
**Ação recomendada:** Manter.

---

## D-DEV-07 — Validação de pares: apenas `ast.parse()`, sem checagem semântica
**Data:** 12/05/2026
**Contexto:** Proposta cita: "AST diff validator — confirmar que pares minerados batem com o tipo de mudança alegado pelo commit; descarta pares ruins do dataset" (Trilha A, sem 1-2).
**O que foi implementado:** `RefactoringPair.validate_python()` em `data/schema.py` apenas parseia AST de `before_code` e `after_code`. Sem verificação de:
- Equivalência funcional (testes passam antes e depois?)
- Tipo de refactoring está coerente com o `smell_type` declarado (Extract Method realmente extraiu helpers? Guard Clauses realmente reduziu nesting?)
- Tamanho mínimo do `before_code` (Long Method precisa ter ≥ 30 linhas)
**Impacto:** Pares com `smell_type` errado, ou trivialmente curtos, passam pela validação. Dataset pode conter ruído alto. Como Trilha A é quem implementa o AST diff validator, este é débito interno da Trilha B só se Trilha A não entregar.
**Ação recomendada:** Adicionar checagens mínimas Trilha-B-side enquanto Trilha A não entrega: comprimento mínimo `before_code` por smell, `len(after_code) != len(before_code)` etc.

---

## D-DEV-08 — Split estratificado por smell_type 80/10/10 sem agrupamento por repo
**Data:** 12/05/2026
**Contexto:** Proposta não fala em split, mas o paradigma comum em mineração de refactorings é "split by repo" (treino e teste não compartilham repositório) para evitar vazamento.
**O que foi implementado:** `DataCurator.split()` usa `StratifiedShuffleSplit` sobre o índice das amostras, estratificado por `smell_type`. Não há GroupShuffleSplit por repo — duas funções do mesmo repositório podem ir para train e test.
**Impacto:** Vazamento metodológico potencial. Modelo pode memorizar idiomas/nomes de uma codebase específica e parecer melhor na avaliação.
**Ação recomendada:** Trocar para `GroupShuffleSplit` por `repo` (ou `StratifiedGroupKFold` quando disponível) — split por repositório, mantendo aproximação estratificada por smell_type.

---

## D-DEV-09 — Mínimo de 5 registros para split (sem mínimo por classe)
**Data:** 12/05/2026
**Contexto:** Sem especificação direta.
**O que foi implementado:** `split()` exige `len(self._pairs) ≥ 5`. Não há mínimo por smell_type. Com 5 pares estratificados em 5 classes (R1-R5), o split 80/10/10 é degenerado.
**Impacto:** Erro silencioso possível — em corpus pequeno (R5=Dead Code pode ser raro), split fica com 0 amostras em val ou test para alguma classe.
**Ação recomendada:** Adicionar validação `min_per_class >= 3` antes de split.

---

## D-DEV-10 — Avaliação execution-based mede `pass_rate_after - pass_rate_before` sem verificar que o teste exercita a função refatorada
**Data:** 12/05/2026
**Contexto:** Proposta: "Avaliação execution-based dos 5 LoRAs — rodar testes do projeto-alvo antes/depois da refatoração; reportar % de testes que continuam passando".
**O que foi implementado:** `evaluation/eval_execution.py` substitui arquivo refatorado, roda `pytest` no projeto, parseia "X passed, Y failed". O delta é reportado. Não há:
- Coverage tracking — pode ser que os testes nem toquem o código refatorado
- Filtragem para testes relacionados à função refatorada
- Mutation testing para validar a sensibilidade do teste à mudança
- Detecção de testes que passam por motivo errado (XFAIL/SKIP/etc.)
**Impacto:** Pass rate pode ficar inalterada por motivo trivial (testes não cobrem a função). Métrica subestima ou superestima qualidade do refactoring.
**Ação recomendada:** Adicionar verificação opcional via `coverage` que a função refatorada é exercitada pelos testes; ou restringir a uma suíte de fixtures.

---

## D-DEV-11 — Parser regex de saída do pytest é frágil
**Data:** 12/05/2026
**Contexto:** Sem especificação.
**O que foi implementado:** `_parse_pytest_output` usa regex `(\d+) passed(?:, (\d+) failed)?(?:, (\d+) error)?`. Não cobre: skipped, xfailed, xpassed, warnings (formato do pytest varia entre versões). Não usa `pytest --json-report` ou `pytest-junit-xml`.
**Impacto:** Em projetos com testes skipped (comum), o count fica errado. Casos com erros de coleta (ImportError) retornam `(0, 0)` silenciosamente.
**Ação recomendada:** Substituir por integração com `pytest-json-report` para parse estruturado.

---

## D-DEV-12 — Sample pairs sintéticos escritos pelo agente, não vindos de mineração real
**Data:** 12/05/2026
**Contexto:** Trilha B depende de Trilha A para minerar pares — proposta diz "Dependências de entrada: precisa do batch minerado da Trilha A (sem 2)".
**O que foi implementado:** `data/sample_pairs/r1_long_method.json` ... `r5_dead_code.json` contêm pares feitos à mão pelo agente (commits = "manual", repo = "example"). Função `process_order`, `generate_report`, `import_users_from_csv` etc. são inventadas.
**Impacto:** Útil como smoke test (D-DEV-13) e como exemplo. **Não substitui** dataset minerado. Treinar LoRAs só com esses pares overfitaria a 3-5 exemplos por smell.
**Ação recomendada:** Manter como `sample_pairs/` para smoke test; documentar que treino real exige mineração da Trilha A.

---

## D-DEV-13 — Smoke test usa `r=4, alpha=8, target=["q_proj","v_proj"]` — divergente do default de produção
**Data:** 12/05/2026
**Contexto:** Sem especificação.
**O que foi implementado:** `scripts/smoke_test.py` instancia LoRA com `r=4, alpha=8, target=["q_proj","v_proj"]`, `lr=1e-4`, sem TrainingArguments — só verifica que `loss > 0` após um forward+backward step. Diferente de `lora_config.py` defaults (r=16, alpha=32, todos os 7 módulos, lr=2e-4).
**Impacto:** Smoke test valida apenas: imports, modelo carrega, PEFT wraps, gradiente flui. Não exercita o config de produção. Falhas específicas do config maior (OOM em fp16/all-linear) não são pegas.
**Ação recomendada:** Manter o smoke test enxuto; adicionar um teste integration que use os defaults reais.

---

## D-DEV-14 — `evaluation_strategy="steps"` e `eval_steps=100` (Transformers legacy)
**Data:** 12/05/2026
**Contexto:** Sem especificação.
**O que foi implementado:** `train_lora.py` linha 146 usa `evaluation_strategy="steps"`. Transformers 4.40+ renomeou para `eval_strategy`; em 4.50+ pode ser depreciado. Como `requirements.txt` pede `transformers>=4.40` (sem upper bound), há risco de quebrar em versões recentes.
**Impacto:** Warning ou erro dependendo da versão.
**Ação recomendada:** Mudar para `eval_strategy="steps"` e pinar `transformers<5.0`.

---

## D-DEV-15 — Tokenizer.pad_token = eos_token (padrão para Qwen mas não documentado)
**Data:** 12/05/2026
**Contexto:** Qwen2.5 não vem com `pad_token` — usuário precisa setar manualmente.
**O que foi implementado:** Em `load_model_and_tokenizer` e `smoke_test`, `tokenizer.pad_token = tokenizer.eos_token` é setado se ausente. Padrão de comunidade, mas faz `eos` ficar mascarado em sequências paddeadas. Para causal LM com `labels = input_ids.clone()`, isso significa que o modelo recebe sinal de gradiente para gerar EOS no fim de cada sequência — desejável. Mas se `padding_side="right"`, EOS pode acabar mascarado em batch padding.
**Impacto:** Aceitável; comportamento padrão. Vale o registro porque pode interagir mal com `packing=False` + `max_seq_length=2048`.
**Ação recomendada:** Manter; verificar `padding_side` é "right" (default) para causal LM.

---

## D-DEV-16 — Diretório `adapters/` vazio (apenas `.gitkeep`)
**Data:** 12/05/2026
**Contexto:** Output dos treinos LoRA.
**O que foi implementado:** Pasta criada via `.gitkeep`. Nenhum adapter treinado ainda.
**Impacto:** Nenhum — só registro.
**Ação recomendada:** Manter.

---

## D-DEV-17 — Sem integração com mineração Trilha A; CLI de curadoria espera JSON/CSV externo
**Data:** 12/05/2026
**Contexto:** Trilha A é responsável pelo PyDriller + AST diff. Trilha B consome a saída.
**O que foi implementado:** `DataCurator.read_raw()` aceita JSON ou CSV. Formato esperado documentado apenas no schema (`schema.py`): `before_code`, `after_code`, `smell_type`, `repo`, `commit_hash`, `function_name?`. Não há contrato escrito entre Trilha A e B nem schema compartilhado em `references/`.
**Impacto:** Risco de mismatch quando Trilha A entregar. Ex: Trilha A pode emitir `smell` em vez de `smell_type`, ou `commit` em vez de `commit_hash`.
**Ação recomendada:** Compartilhar o pydantic schema (ou um JSON-Schema derivado) entre as duas trilhas; adicionar adapter de campos em `curate.py`.

## D-DEV-18 — Schema unificado em `core/` como contrato A↔B
**Data:** 18/05/2026
**Contexto:** D-DEV-17 apontou o risco de mismatch entre o formato emitido pela Trilha A (`before/after/smell/commit/name`) e o esperado pela Trilha B (`before_code/after_code/smell_type/commit_hash/function_name`). A reanálise confirmou que o mismatch já era real — o `DataCurator` não leria a saída do minerador. Os tipos `FunctionInfo`/`ClassInfo` também estavam duplicados em `extracao/mineracao/data_structs.py` e `detectores/data_structs.py`.
**O que foi implementado:** Pacote `core/` no topo do repo — `core/smells.py` (vocabulário canônico R1–R5 + nomes/refatorações), `core/ast_types.py` (`FunctionInfo`/`ClassInfo` unificados) e `core/schema.py` (`RefactoringPair` Pydantic, contrato único, com os campos novos `id`, `commit_msg`, `msg_keywords`, `metrics_*`, `verified`, `detector_*`, `parent_commit`, `n_functions_after`, bloco `review`). `trilha_b/data/schema.py` e os dois `data_structs.py` passam a re-exportar de `core/`.
**Impacto:** Fecha D-DEV-17. Os campos preenchidos pelo minerador/curador são opcionais com default — fixtures antigas (`trilha_b/data/sample_pairs/*.json`) continuam válidas. Trilha A e B passam a ter uma fonte única de verdade.
**Ação recomendada:** O minerador (Trilha A) deve emitir registros que validam contra `core.schema.RefactoringPair`. Remover os shims de `data_structs.py`/`schema.py` num ciclo futuro.

<!-- Adicionar novas decisões aqui: D-DEV-19, D-DEV-20, etc. -->
