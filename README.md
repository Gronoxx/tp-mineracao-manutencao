# TP — Mineração de Repositórios: Detecção e Refatoração de Code Smells em Python

Trabalho Prático da disciplina **Engenharia de Software II** — UFMG.

---

## 1. Membros do Grupo

- Gustavo Dias Apolinário
- Bernardo Vale dos Santos Bento
- Filipe Mauro da Terra Caldeira

---

## 2. Sobre o Sistema

Ferramenta de linha de comando (CLI) que **identifica 12 code smells em código Python e sugere refatorações automaticamente** para um subset desses smells, a partir da mineração de repositórios Git/GitHub. O fluxo é totalmente automatizado da entrada (arquivo ou repositório) à saída (lista de diffs sugeridos); a única etapa humana é a **aprovação final de cada diff** pelo usuário.

A escolha do mecanismo de detecção (regras estáticas vs. ML) é **per-smell**, justificada pela literatura empírica acumulada de 1976 a 2026 (vide catálogo de evidências em `docs/`). ML é adotado apenas onde há evidência consistente de gap sobre regras (Beyazit et al. 2026; Liu et al. 2018, 2023; Kovačević et al. 2022); regras são adotadas onde a literatura confirma equivalência ou superioridade, ou onde o problema é estruturalmente determinístico via AST.

### Os 12 smells cobertos

Organizados em três camadas, com detecção em mecanismos distintos:

#### Camada 1 — Regras estáticas core (5 smells)

| # | Smell | Mecanismo | Detalhe |
|---|---|---|---|
| 1 | **Long Method** | Lizard `-L 30` + Pylint R0915/R0912 | F1 0.84 cross-project (Beyazit 2026); gap +3pp para ML não justifica complexidade |
| 2 | **Long Parameter List** | AST parameter count (stdlib) | Regras vencem ML por 6pp (Beyazit 2026) |
| 3 | **Magic Numbers / Strings** | ruff PLR2004 + extensão AST custom | Cobre comparações + assignments + strings |
| 4 | **Deeply Nested Conditional** | pylint R1702 (threshold 3) | Contagem AST exata |
| 5 | **Dead Code intra-função** | pylint W0101+W0612+W0613 + vulture | ~70% casos sintáticos cobertos |

#### Camada 2 — Regras estáticas adicionais (4 smells)

| # | Smell | Mecanismo | Detalhe |
|---|---|---|---|
| 6 | **Refused Bequest** | MRO traversal + override count | Regras vencem ML por 7pp (Beyazit 2026) |
| 7 | **Duplicate Code Tipo-1/2/3** | NiCad (Python support) ou AST hash | Regras textuais/sintáticas saturadas (~F1 0.95) |
| 8 | **Long Message Chain** | Algoritmo PyExamine portado | Contagem de chamadas encadeadas |
| 9 | **Middle Man** | Algoritmo PyExamine portado, intra-arquivo | Razão de delegação por método |

#### Camada 3 — Detecção ML class-scope (3 smells)

| # | Smell | Mecanismo | F1 esperado em Python |
|---|---|---|---|
| 10 | **Feature Envy** | Qwen2.5-Coder-1.5B + LoRA classifier head | ~0.65–0.80 |
| 11 | **God Class / Blob** | Mesmo modelo base, LoRA classifier separado | ~0.70–0.85 |
| 12 | **Data Class** | Mesmo modelo base, LoRA classifier separado | ~0.70–0.85 |

ML é justificado para esses três pela literatura recente (Beyazit 2026: gaps de +8pp, +23-28pp, +11pp respectivamente em ground truth humano cross-project).

### Stack ML unificado

A detecção ML class-scope e a refatoração via LoRAs compartilham **um único modelo base** carregado em memória — Qwen2.5-Coder-1.5B. Adaptadores LoRA são swapados conforme a tarefa:

- **7 LoRAs de refatoração**: Long Method (Extract Method), Long Parameter List (Introduce Parameter Object), Magic Numbers (Replace with Named Constant), Deep Nesting (Guard Clauses), Dead Code (Remove), Feature Envy (Move Method), God Class (Extract Class)
- **3 LoRAs de classificação**: Feature Envy, God Class, Data Class — multilabel sigmoid head sobre embedding da classe
- **1 LoRA classifier de Long Method** — treinado apenas para **ablação científica no paper** (comparação rules vs. ML), não usado na pipeline de produção

Total: **11 LoRAs sobre o mesmo modelo base**. Cada LoRA pesa 5–50 MB e treina em 1–3h em GPU gratuita (Google Colab/Kaggle).

### Por que essa arquitetura

A decisão arquitetural reflete três princípios:

- **Honestidade da evidência:** ML é adotado apenas onde a literatura recente (cross-project, ground truth humano, pós-Di Nucci 2018) mostra gap consistente. Para 9 dos 12 smells, regras são equivalentes ou superiores — usar ML neles seria overengineering.
- **Reuso de infraestrutura:** o mesmo pipeline de mineração via PyDriller serve simultaneamente o treinamento dos LoRAs de refatoração e dos LoRAs de classificação. Um único modelo base. Uma única coleção de pares minerados.
- **Operação 100% offline:** sem APIs externas. Toda inferência roda localmente em Qwen2.5-Coder-1.5B (~2GB RAM) com adaptadores LoRA leves swapados conforme necessário.

### Pipeline de uso

1. Usuário aponta a CLI para um arquivo Python individual ou diretório.
2. **Decomposição AST**: cada arquivo é particionado em funções/métodos (`ast.FunctionDef`) e classes (`ast.ClassDef`).
3. Para cada função/método: detectores estáticos das camadas 1 e 2 verificam smells aplicáveis.
4. Para cada classe: detectores estáticos da camada 2 (Refused Bequest, Duplicate, Long Chain, Middle Man) + LoRA classifiers da camada 3 (Feature Envy, God Class, Data Class) executam em paralelo.
5. Para cada smell detectado em que há LoRA de refatoração disponível (7 dos 12), o LoRA correspondente gera a versão refatorada.
6. Para os outros 5 smells (Refused Bequest, Duplicate, Long Message Chain, Middle Man, Data Class): a ferramenta apenas reporta o smell com sugestão textual (sem geração automática).
7. Resultados agregados em árvore hierárquica refletindo a estrutura do código. Usuário inspeciona diffs e aprova/rejeita cada um.

### Saída em árvore

```
projeto/
├── src/parser.py
│   ├── class Tokenizer                      [God Class (0.78)]  → sugestão Extract Class
│   │   ├── tokenize()
│   │   │     iter 1: Long Method (rule)     → extract _scan_token()
│   │   │     iter 2: Magic Numbers (rule)   → constante TOKEN_MAX_LEN
│   │   │     iter 3: clean
│   │   ├── _peek()                          clean
│   │   └── _consume()
│   │         iter 1: Magic Numbers (rule)   → constante BUFFER_SIZE
│   │         iter 2: clean
│   └── helper_normalize()
│         iter 1: Deep Nesting (rule)        → guard clauses
│         iter 2: clean
└── src/cli.py
    ├── class CliRunner                      [Feature Envy (0.71)]  → sugestão Move Method
    └── main()
          iter 1: Long Parameter List (rule) → CliConfig dataclass
          iter 2: clean
```

### Construção do dataset (compartilhada)

O pipeline de mineração via PyDriller serve simultaneamente:

- **Treino dos 7 LoRAs de refatoração**: pares `(antes, depois)` extraídos de commits cuja mensagem mencione palavras-chave (`extract method`, `rename parameter`, `introduce constant`, `flatten nesting`, `remove dead code`, `move method`, `extract class`/`split class`).
- **Treino dos 4 LoRAs de classificação**: o `(antes, smell_label)` é derivado dos mesmos pares — função/classe "antes" é positiva para o smell endereçado pelo commit.

Validação automática via AST diff confirma que cada par bate com o tipo de mudança alegado pela mensagem. Pares descartados se inconsistentes.

Datasets externos complementares para validação cruzada:
- **MLCQ** (Madeyski & Lewowski 2020): 14k+ samples Java rotulados por 26 desenvolvedores; usado para transfer learning quando aplicável.
- **SmellyCode++** (Alomari et al. 2025): ~107k Java samples para God Class, Data Class, Feature Envy, Long Method.
- **GPTCloneBench** (ICSME 2023): 37k+ pares semantic clones inclui Python — disponível se Type-4 clones for incluído (decisão pendente do trio).

### Avaliação

**Detecção:**
- Held-out manual: ~50 funções + ~30 classes Python rotuladas por 2-3 anotadores (kappa reportado).
- Métricas: precision, recall, F1 por smell; macro-F1 multilabel para classifiers ML.
- **Ablação Long Method**: tabela comparativa rules vs. ML classifier reportada no paper.

**Refatoração:**
- Execution-based: testes do projeto-alvo passam após refatoração?
- Avaliação humana: micro-survey 3-5 avaliadores em escala de qualidade (idiomaticidade, clareza, granularidade).

**Baselines comparativos:**
- **B0** — Llama-3.3 zero-shot (modelo grande, apenas para ablação)
- **B1** — LoRA único multitask (todos smells juntos)
- **B2** — Oracle routing (limite superior)
- **B3** — Rope (refatoração mecânica rule-based)

A inclusão de **B3** é metodologicamente central: posiciona "fully-neural fine-tuned" vs. "rule-based mechanical" como duas filosofias completas. Sistema neural precisa **empatar com Rope em corretude execution-based** e **ganhar em qualidade subjetiva**.

### Decisão pendente do trio: workarounds opcionais

Três smells antes "fora do escopo" tiveram workarounds confirmados como viáveis:

- **Type-4 semantic clones**: UniXcoder zero-shot + GPTCloneBench Python pairs (~1-2 sem extras, sem mudança no input)
- **Shotgun Surgery / Divergent Change**: PyDriller + co-change heuristic (~2-3 sem extras, requer flag `--repo-path`)

A inclusão depende do balanceamento escopo vs. profundidade que o trio decidir.

---

## 3. Tecnologias Possíveis

### Mineração de repositórios

- [**PyDriller**](https://github.com/ishepard/pydriller) — framework Python para análise de repositórios Git; principal ferramenta de mineração de pares para LoRAs e classifiers.
- [**GitPython**](https://github.com/gitpython-developers/GitPython) — apoio para operações Git de baixo nível.
- [**PyGithub**](https://github.com/PyGithub/PyGithub) — integração com a API do GitHub para enriquecer o dataset com issues e PRs.

### Decomposição e análise estática (camadas 1 e 2)

- [**ast (stdlib do Python)**](https://docs.python.org/3/library/ast.html) — análise sintática nativa para particionar arquivos em funções/classes e extrair features.
- [**Lizard**](https://github.com/terryyin/lizard) — métricas de complexidade ciclomática e LOC; insumo principal para Long Method.
- [**radon**](https://github.com/rubik/radon) — Halstead, Maintainability Index, complexidade.
- [**Pylint**](https://github.com/pylint-dev/pylint) — R0915, R0912, R0913, R1702, W0101, W0612, W0613 — base para múltiplos detectores estáticos.
- [**Ruff**](https://github.com/astral-sh/ruff) — PLR2004 (Magic Numbers em comparações) + integração rápida com formato JSON.
- [**Vulture**](https://github.com/jendrikseipp/vulture) — Dead Code com confidence scoring (60-100%).
- [**PyExamine**](https://github.com/KarthikShivasankar/python_smells_detector) — referência algorítmica para Long Message Chain e Middle Man.

### Refatoração mecânica (baseline B3)

- [**Rope**](https://github.com/python-rope/rope) — biblioteca de refactoring para Python; usada como **baseline B3** (rule-based mechanical) e como gerador de silver labels para mineração.

### Modelo base e fine-tuning (camada 3 + LoRAs de refatoração)

- [**HuggingFace Transformers**](https://github.com/huggingface/transformers) — carregamento e inferência.
- [**HuggingFace PEFT**](https://github.com/huggingface/peft) — implementação de adaptadores LoRA.
- [**HuggingFace TRL**](https://github.com/huggingface/trl) — pipeline de fine-tuning supervisionado.
- [**Qwen2.5-Coder-1.5B**](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B) — **modelo base unificado** para todos os 11 LoRAs (7 refatoração + 3 classificação class-scope + 1 ablação Long Method).
- [**CodeT5-base**](https://huggingface.co/Salesforce/codet5-base) — alternativa de modelo base candidata (decisão final na fase de prototipação).

### Workarounds opcionais (camada 4, decisão do trio)

- [**UniXcoder**](https://huggingface.co/microsoft/unixcoder-base) — encoder pré-treinado em 9 linguagens incluindo Python; zero-shot embedding similarity para detecção de Type-4 clones.
- [**GPTCloneBench**](https://zenodo.org/records/10198952) — benchmark de 37k+ pares de clones Tipo-4 incluindo Python (CC BY-NC-ND).

### Interface de linha de comando

- [**Typer**](https://github.com/fastapi/typer) — definição declarativa da CLI.
- [**Rich**](https://github.com/Textualize/rich) — formatação de saída no terminal, renderização nativa da árvore hierárquica e exibição de diffs.

### Avaliação

- [**pytest**](https://github.com/pytest-dev/pytest) — execução dos testes do repositório-alvo (avaliação execution-based).
- [**scikit-learn**](https://scikit-learn.org) — métricas (precision, recall, F1, macro-F1, MCC) e baselines.
- [**pandas**](https://pandas.pydata.org) — agregação dos resultados experimentais.

### Reprodutibilidade e ambiente

- **Docker** — empacotamento do ambiente de execução completo (modelo base + LoRAs + ferramentas estáticas).
- **Make** — automação da pipeline (`make all` reproduz tabelas e figuras do relatório).
- **Google Colab** ou **Kaggle Notebooks** — ambiente de treinamento (GPU gratuita, 16 GB).

### Origem dos dados

A coleta primária combina **Git local** (via PyDriller, sem rate limit) e **GitHub API** (via PyGithub, para enriquecer dataset com issues/PRs). Repositórios-alvo selecionados via [**Seart GitHub Search (GHS)**](https://seart-ghs.si.usi.ch) com filtros de popularidade, atividade e linguagem (Python).

Datasets externos para validação cruzada:
- **MLCQ** ([Zenodo](https://zenodo.org/records/3666840)) — Madeyski & Lewowski 2020.
- **SmellyCode++** ([Figshare](https://doi.org/10.6084/m9.figshare.28519385.v1)) — Alomari et al. 2025.
- **GPTCloneBench** ([Zenodo](https://zenodo.org/records/10198952)) — apenas se Type-4 clones for incluído pela decisão do trio.

---

*Engenharia de Software II — UFMG — 2026*
