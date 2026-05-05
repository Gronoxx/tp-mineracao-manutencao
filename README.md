# TP — Mineração de Repositórios: Detecção e Refatoração de Code Smells em Funções Python

Trabalho Prático da disciplina **Engenharia de Software II** — UFMG.

---

## 1. Membros do Grupo

- Gustavo Dias Apolinário
- Bernardo Vale dos Santos Bento
- Filipe Mauro da Terra Caldeira

---

## 2. Sobre o Sistema

Ferramenta de linha de comando (CLI) que **identifica code smells em nível de função em código Python e sugere refatorações automaticamente**, a partir da mineração de repositórios Git/GitHub. Diferente de abordagens tradicionais que apenas reportam métricas (LOC, complexidade, churn), o sistema atua em duas etapas neurais conectadas por um mecanismo de roteamento:

1. **Classificador leve** — recebe uma função e prevê a qual das cinco classes de smell ela pertence (ou se está limpa).
2. **Adaptadores especializados (LoRA)** — uma vez identificada a classe, o sistema invoca o adaptador correspondente, treinado especificamente para refatorar aquele tipo de smell, e gera uma sugestão de versão refatorada.

### Escopo: smells intra-função

Restringimos deliberadamente o escopo a **smells que vivem dentro de uma função** (não cobrimos God Class, Shotgun Surgery, Divergent Change ou outros smells de nível de classe / projeto). Três motivos técnicos justificam o recorte:

- A função é a unidade natural para um modelo base de 1.5B parâmetros: cabe no contexto sem truncamento e tem fronteiras semânticas claras.
- Smells intra-função têm critérios de detecção objetivos (LOC, complexidade ciclomática, número de parâmetros, profundidade de aninhamento), o que torna o *ground truth* tratável.
- A decomposição de um arquivo em funções é determinística via AST do Python — não precisa de ML.

### Os cinco smells atacados

Todos retirados do catálogo de Fowler (*Refactoring*, 2nd ed., 2018) e cobertos por literatura acadêmica de detecção de smells (Tsantalis, Palomba, Madeyski-Lewowski).

| # | Smell | Detecção (regra) | Refatoração-alvo (ML) |
|---|---|---|---|
| 1 | **Long Method** | LOC > 30 ou CC > 10 | Extract Method — escolher onde cortar |
| 2 | **Long Parameter List** | nº parâmetros > 4 | Introduce Parameter Object |
| 3 | **Magic Numbers / Strings** | literais não-triviais no corpo | Replace with Named Constant |
| 4 | **Deeply Nested Conditional** | profundidade de aninhamento > 3 | Guard Clauses / Decompose Conditional |
| 5 | **Dead Code intra-função** | branches inalcançáveis, vars não usadas | Remover (ML atua como filtro de falso positivo) |

### Por que essa arquitetura

**Detectar** esses smells é relativamente trivial via heurística estática. **Gerar uma refatoração correta** é o problema difícil — onde dividir um Long Method, quais parâmetros agrupar em um objeto, qual nome semântico dar a uma constante mágica, qual estratégia escolher para desaninhar um conditional. O esforço de ML do projeto está concentrado nesse ponto.

Nesse arranjo, cada componente tem um papel claro:

- **Regras heurísticas** dão *recall* (encontram todos os candidatos a smell).
- **Classificador leve** dá *precision* (filtra falsos positivos das regras e seleciona o adaptador apropriado).
- **Adaptadores LoRA** geram a refatoração.

Os adaptadores LoRA (Low-Rank Adaptation) permitem manter cinco geradores especializados sem o custo proibitivo de treinar e armazenar cinco modelos completos: todos os adaptadores compartilham o **mesmo modelo base** pré-treinado, e o roteador apenas troca qual adaptador está ativo durante a inferência. Cada adaptador pesa entre 5-50 MB e treina em GPU gratuita (Google Colab / Kaggle).

### Pipeline de uso

1. Usuário aponta a CLI para um repositório Python (caminho local ou URL Git) ou para um arquivo individual.
2. O sistema clona/atualiza o repositório e percorre os arquivos `.py`.
3. **Decomposição AST**: cada arquivo é particionado em funções e métodos (`ast.FunctionDef`, `ast.AsyncFunctionDef`) — operação determinística, sem ML.
4. Para cada função: regras heurísticas filtram candidatos → classificador confirma a classe (ou descarta como falso positivo) → adaptador LoRA correspondente gera a sugestão de refatoração.
5. Os resultados são agregados em uma **árvore hierárquica** que reflete a estrutura do código.

### Saída em árvore

```
projeto/
├── src/parser.py
│   ├── class Tokenizer
│   │   ├── tokenize()           [Long Method]         → sugestão de extract
│   │   ├── _peek()              [clean]
│   │   └── _consume()           [Magic Numbers]       → sugestão de constante
│   └── helper_normalize()       [Deep Nesting]        → sugestão de guard clauses
└── src/cli.py
    └── main()                   [Long Parameter List] → sugestão de parameter object
```

A agregação em árvore tem um bônus arquitetural: contagem de smells por classe pode sinalizar smells de nível mais alto (ex.: classes com mais de 70% dos métodos flagueados como Long Method tendem a ser God Class), abrindo uma extensão natural do trabalho **sem retreinamento**. Não é objetivo do TP, mas a arquitetura habilita.

### Avaliação

A qualidade das refatorações será avaliada de forma **execution-based** (o código refatorado continua passando nos testes originais do repositório?) e por **avaliação humana** em micro-survey (3-5 avaliadores classificam as refatorações em uma escala de qualidade). Os baselines comparativos são:

- **B0** — modelo base sem fine-tuning, em modo zero-shot.
- **B1** — um único modelo fine-tunado com a união das cinco classes (multitask).
- **B2** — especialistas com roteamento perfeito (*oracle routing*) — limite superior do roteador.
- **B3** — refatoração mecânica via [Rope](https://github.com/python-rope/rope), biblioteca clássica de refactoring para Python.

A inclusão de **B3** é metodologicamente importante: para o sistema neural se justificar, ele precisa ao menos **empatar com o Rope em corretude** (passa nos testes) e **ganhar em qualidade subjetiva** (idiomaticidade, escolha de nomes, granularidade da decomposição) na avaliação humana.

---

## 3. Tecnologias Possíveis

A lista abaixo reúne as tecnologias candidatas para cada componente do sistema. A escolha final entre alternativas será feita ao longo da implementação, conforme as restrições práticas (custo computacional, qualidade do dataset gerado, integração).

### Mineração de repositórios

- [**PyDriller**](https://github.com/ishepard/pydriller) — framework Python para análise de repositórios Git; principal ferramenta para extração de pares (versão antes / versão depois de um commit de refatoração).
- [**GitPython**](https://github.com/gitpython-developers/GitPython) — biblioteca para operações Git de baixo nível (apoio).
- [**PyGithub**](https://github.com/PyGithub/PyGithub) — integração com a API do GitHub para coleta de issues, PRs e metadados que enriquecem o dataset.

### Decomposição e análise estática

- [**ast (stdlib do Python)**](https://docs.python.org/3/library/ast.html) — análise sintática nativa para particionar arquivos em funções/métodos e extrair features para o classificador.
- [**Lizard**](https://github.com/terryyin/lizard) — métricas de complexidade ciclomática multi-linguagem (insumo para regras de detecção).
- [**radon**](https://github.com/rubik/radon) — métricas adicionais para código Python (Halstead, Maintainability Index).
- [**tree-sitter**](https://github.com/tree-sitter/tree-sitter) — fallback para parsing genérico se necessário.

### Refatoração mecânica (baseline B3)

- [**Rope**](https://github.com/python-rope/rope) — biblioteca de refactoring para Python, usada como **baseline B3** comparativo. Implementa Extract Method, Introduce Parameter, Rename, entre outros.

### Modelo base e fine-tuning

- [**HuggingFace Transformers**](https://github.com/huggingface/transformers) — carregamento e inferência dos modelos pré-treinados.
- [**HuggingFace PEFT**](https://github.com/huggingface/peft) — implementação de adaptadores LoRA.
- [**HuggingFace TRL**](https://github.com/huggingface/trl) — pipeline de fine-tuning supervisionado.
- [**Qwen2.5-Coder-1.5B**](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B) ou [**CodeT5-base**](https://huggingface.co/Salesforce/codet5-base) — modelo base candidato para geração de código.
- [**CodeBERT**](https://huggingface.co/microsoft/codebert-base) — embeddings de entrada para o classificador leve.

### Interface de linha de comando

- [**Typer**](https://github.com/fastapi/typer) — definição declarativa da CLI (escolha principal).
- [**Rich**](https://github.com/Textualize/rich) — formatação de saída no terminal, com renderização nativa da árvore hierárquica de resultados.

### Avaliação

- [**pytest**](https://github.com/pytest-dev/pytest) — execução dos testes do repositório-alvo sobre o código refatorado (avaliação *execution-based*).
- [**scikit-learn**](https://scikit-learn.org) — métricas do classificador (precision, recall, F1) e baselines.
- [**pandas**](https://pandas.pydata.org) — agregação dos resultados experimentais.

### Reprodutibilidade e ambiente

- **Docker** — empacotamento do ambiente de execução.
- **Make** — automação da pipeline (`make all` reproduz tabelas e figuras do relatório).
- **Google Colab** ou **Kaggle Notebooks** — ambiente de treinamento (GPU gratuita, 16 GB).

### Origem dos dados

A coleta combina **Git local** (via PyDriller, sem rate limit, foco em diffs e mensagens de commit que mencionam refatoração) e **GitHub API** (via PyGithub, para enriquecer o dataset com informações de issues e PRs ligadas a commits de refatoração). Repositórios-alvo serão selecionados via [**Seart GitHub Search (GHS)**](https://seart-ghs.si.usi.ch) com filtros de popularidade, atividade e linguagem (Python).

Datasets públicos como **MLCQ** (Madeyski & Lewowski, 2020) podem servir como *ground truth* complementar para validação cruzada do classificador.

---

*Engenharia de Software II — UFMG — 2026*
