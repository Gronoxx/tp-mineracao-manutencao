# TP — Mineração de Repositórios: Detecção e Refatoração de Code Smells em Funções Python

Trabalho Prático da disciplina **Engenharia de Software II** — UFMG.

---

## 1. Membros do Grupo

- Gustavo Dias Apolinário
- Bernardo Vale dos Santos Bento
- Filipe Mauro da Terra Caldeira

---

## 2. Sobre o Sistema

Ferramenta de linha de comando (CLI) que **identifica code smells em nível de função em código Python e sugere refatorações automaticamente**, a partir da mineração de repositórios Git/GitHub. O fluxo é **totalmente automatizado** da entrada (arquivo ou repositório) à saída (lista de diffs sugeridos); **a única etapa humana é a aprovação final de cada diff** pelo usuário. O sistema atua em duas etapas neurais conectadas por um mecanismo de roteamento:

1. **Classificador single-label iterativo** — recebe uma função e atribui probabilidades a **6 classes** (5 smells + 1 classe `clean`) via *softmax*. Em cada passada, o smell de maior probabilidade é selecionado.
2. **Adaptadores especializados (LoRA)** — uma vez identificado o smell dominante, o adaptador correspondente gera a refatoração. A função refatorada **volta ao classificador em uma nova iteração**; o ciclo continua até a classe `clean` ser predita ou um critério de parada ser atingido.

### Escopo: smells intra-função

Restringimos deliberadamente o escopo a **smells que vivem dentro de uma função** (não cobrimos God Class, Shotgun Surgery, Divergent Change ou outros smells de nível de classe / projeto). Três motivos técnicos justificam o recorte:

- A função é a unidade natural para um modelo base de 1.5B parâmetros: cabe no contexto sem truncamento e tem fronteiras semânticas claras.
- Smells intra-função têm sinais estruturais objetivos (LOC, complexidade ciclomática, número de parâmetros, profundidade de aninhamento) que o classificador aprende a detectar a partir dos dados, sem necessidade de heurísticas *hardcoded*.
- A decomposição de um arquivo em funções é determinística via AST do Python — não precisa de ML.

### Os cinco smells atacados

Todos retirados do catálogo de Fowler (*Refactoring*, 2nd ed., 2018) e cobertos por literatura acadêmica de detecção de smells (Tsantalis, Palomba, Madeyski-Lewowski).

| # | Smell | Sinais característicos | Refatoração-alvo (LoRA) |
|---|---|---|---|
| 1 | **Long Method** | LOC alto, CC alta, múltiplas responsabilidades | Extract Method — escolher onde cortar |
| 2 | **Long Parameter List** | número de parâmetros alto, parâmetros logicamente correlacionados | Introduce Parameter Object |
| 3 | **Magic Numbers / Strings** | literais não-triviais usados sem nome semântico | Replace with Named Constant |
| 4 | **Deeply Nested Conditional** | profundidade de aninhamento elevada, lógica de fluxo embolada | Guard Clauses / Decompose Conditional |
| 5 | **Dead Code intra-função** | branches inalcançáveis, variáveis e parâmetros não usados | Remover (com confirmação de equivalência semântica) |

### Por que essa arquitetura

A escolha foi por uma pipeline **fully-neural end-to-end**: tanto a detecção quanto a geração da refatoração são feitas por modelos treinados, sem heurísticas estáticas no caminho de inferência. Três motivos justificam:

- **Limiares são contextuais.** Uma função de teste pode tolerar mais LOC; uma função de I/O pode tolerar mais aninhamento. Regras com limiares fixos não capturam contexto. Um classificador treinado em código real aprende a tolerar variações que humanos toleram.
- **Composição iterativa reflete o processo real de refatoração.** Refatorações cascateiam: extrair um método muda quais parâmetros são longos, quais constantes mágicas remanescentes ainda existem, e onde os aninhamentos profundos persistem. Tratar um smell de cada vez e re-classificar o resultado captura essa dinâmica; estratégias *one-shot* ignoram a interação entre passos.
- **Escalabilidade do design.** Adicionar um sexto smell no futuro é adicionar uma sexta classe ao classificador e um sexto adaptador, sem reescrita de regras de engenharia.

Os adaptadores LoRA (Low-Rank Adaptation) permitem manter cinco geradores especializados sem o custo proibitivo de treinar e armazenar cinco modelos completos: todos os adaptadores compartilham o **mesmo modelo base** pré-treinado, e o roteador apenas troca qual adaptador está ativo durante a inferência. Cada adaptador pesa entre 5-50 MB e treina em GPU gratuita (Google Colab / Kaggle).

### Estratégia de detecção: iterativo vs. multilabel

A configuração padrão é o classificador single-label iterativo (6 classes via *softmax*). Em paralelo, uma cabeça de classificação **multilabel** (sigmoid por classe) é treinada sobre o **mesmo encoder**, com custo marginal mínimo, para servir como *fallback* empírico.

Critério de seleção, avaliado no held-out manual:

- **Iterativo vence** se *exact-match rate* da sequência de classificações > 70% em funções com múltiplos smells **e** média de iterações por função < 2.5.
- **Caso contrário**, adota-se a cabeça multilabel one-shot.

Esse experimento comparativo entra no relatório como uma RQ secundária — *qual estratégia de roteamento serve melhor para refatoração iterativa de funções?* Custa pouco (uma cabeça extra de classificação sobre o mesmo encoder) e gera evidência publicável.

### Pipeline de uso

1. Usuário aponta a CLI para um repositório Python (caminho local ou URL Git) ou para um arquivo individual.
2. O sistema clona/atualiza o repositório e percorre os arquivos `.py`.
3. **Decomposição AST**: cada arquivo é particionado em funções e métodos (`ast.FunctionDef`, `ast.AsyncFunctionDef`) — operação determinística, sem ML.
4. Para cada função, executa-se o **loop iterativo de refatoração**:
   - O classificador prediz a classe (5 smells ou `clean`) via *softmax*.
   - Se `clean`, encerra para essa função.
   - Caso contrário, o adaptador LoRA do smell predito gera a versão refatorada.
   - A versão refatorada volta ao classificador e o ciclo se repete.
   - **Critérios de parada adicionais:** (a) máximo de `K=5` iterações; (b) confiança máxima abaixo de limiar mínimo; (c) oscilação entre dois smells em iterações consecutivas. Em (b) e (c), a função é flagada para revisão humana.
5. Os resultados são agregados em uma **árvore hierárquica** que reflete a estrutura do código, com o **trace iterativo** completo de cada função. O usuário inspeciona os diffs sugeridos (passo a passo) e aprova/rejeita cada um — **a aprovação final é a única etapa humana do pipeline**.

### Saída em árvore

```
projeto/
├── src/parser.py
│   ├── class Tokenizer
│   │   ├── tokenize()
│   │   │     iter 1: Long Method (0.91)    → extract _scan_token()
│   │   │     iter 2: Magic Numbers (0.74)  → constante TOKEN_MAX_LEN
│   │   │     iter 3: clean                 → done (3 iterações)
│   │   ├── _peek()                         clean (0 iterações)
│   │   └── _consume()
│   │         iter 1: Magic Numbers (0.82)  → constante BUFFER_SIZE
│   │         iter 2: clean
│   └── helper_normalize()
│         iter 1: Deep Nesting (0.78)       → guard clauses
│         iter 2: clean
└── src/cli.py
    └── main()
          iter 1: Long Parameter List (0.85) → CliConfig dataclass
          iter 2: clean
```

Cada função produz um **trace iterativo** que mostra cada smell endereçado, na ordem detectada, com a refatoração aplicada. O trace é parte do output da CLI e da avaliação — ajuda o usuário a entender o raciocínio passo a passo e o avaliador a auditar o sistema. Como bônus arquitetural, contagem de smells por classe ao longo dos traces pode sinalizar smells de nível mais alto (ex.: classes com mais de 70% dos métodos flagueados como Long Method tendem a ser God Class), abrindo uma extensão natural do trabalho **sem retreinamento**. Não é objetivo do TP, mas a arquitetura habilita.

### Construção do dataset

Como a detecção é fully-neural, a qualidade do classificador depende diretamente da qualidade dos rótulos. A coleta combina três fontes complementares:

- **Fonte primária — refactoring commits via PyDriller.** Filtragem de commits cuja mensagem mencione palavras-chave de cada smell (`extract method`, `rename parameter`, `introduce constant`, `flatten nesting`, `remove dead code`). A função *antes* do commit é exemplo positivo daquele smell; a função *depois* serve como entrada potencial da próxima iteração — pode conter outros smells remanescentes, e preservar isso é importante para o **realismo distribucional** do treino dos LoRAs (eles precisam ver entradas parcialmente refatoradas, não apenas funções "100% sujas"). Validação automática via *AST diff* confirma que o tipo de mudança bate com o que a mensagem alega. Esse processo gera naturalmente **rótulos single-label**: cada commit endereça um smell, então cada par `(antes, depois)` recebe uma label única correspondente ao smell endereçado pelo commit.
- **Fonte secundária — bootstrap via análise estática.** Ferramentas como Pylint, Lizard e Rope geram **silver labels** para uma primeira iteração de treino. Um subconjunto é então revisado manualmente pelos autores para corrigir erros sistemáticos antes do retreino final.
- **Fonte terciária — held-out manual.** Os autores rotulam manualmente cerca de 100 funções por classe (~600 funções no total) exclusivamente para o conjunto de **avaliação**, garantindo que a métrica final seja honesta e independente das heurísticas de mineração.

A mineração serve simultaneamente os dois modelos: cada par `(antes, depois)` extraído fornece `(antes, smell_label)` para o classificador e `(antes, depois)` condicionado em `smell_label` para o adaptador LoRA correspondente.

### Avaliação

A qualidade do sistema será avaliada em três dimensões, com baselines comparativos:

- **Classificação:** precision, recall, F1 por classe e *macro-F1* (head single-label e head multilabel comparados); *exact-match rate* da sequência de classificações no loop iterativo; distribuição do número de iterações por função (média, p95).
- **Refatoração — corretude:** *execution-based* — o código refatorado continua passando nos testes originais do repositório-alvo.
- **Refatoração — qualidade subjetiva:** micro-survey com 3-5 avaliadores externos classificando refatorações em escala de qualidade (idiomaticidade, clareza, granularidade da decomposição).

Baselines comparativos:

- **B0** — modelo base sem fine-tuning, em modo zero-shot.
- **B1** — um único modelo fine-tunado com a união das cinco classes (multitask).
- **B2** — especialistas com roteamento perfeito (*oracle routing*) — limite superior do roteador.
- **B3** — refatoração mecânica via [Rope](https://github.com/python-rope/rope), biblioteca clássica baseada em regras + transformações mecânicas.

A inclusão de **B3** é metodologicamente central: a comparação não é "ML auxilia regras" — é **fully-neural end-to-end vs. rule-based mechanical**, duas filosofias completas lado a lado. Para o sistema neural se justificar, ele precisa **empatar com Rope em corretude execution-based** e **ganhar em qualidade subjetiva** na avaliação humana.

---

## 3. Tecnologias Possíveis

A lista abaixo reúne as tecnologias candidatas para cada componente do sistema. A escolha final entre alternativas será feita ao longo da implementação, conforme as restrições práticas (custo computacional, qualidade do dataset gerado, integração).

### Mineração de repositórios

- [**PyDriller**](https://github.com/ishepard/pydriller) — framework Python para análise de repositórios Git; principal ferramenta para extração de pares (versão antes / versão depois de um commit de refatoração).
- [**GitPython**](https://github.com/gitpython-developers/GitPython) — biblioteca para operações Git de baixo nível (apoio).
- [**PyGithub**](https://github.com/PyGithub/PyGithub) — integração com a API do GitHub para coleta de issues, PRs e metadados que enriquecem o dataset.

### Decomposição e análise estática (suporte à mineração e features)

- [**ast (stdlib do Python)**](https://docs.python.org/3/library/ast.html) — análise sintática nativa para particionar arquivos em funções/métodos e validar mudanças estruturais (*AST diff*) na mineração.
- [**Lizard**](https://github.com/terryyin/lizard) — métricas de complexidade ciclomática multi-linguagem; usadas como **features auxiliares** concatenadas aos embeddings do classificador e como filtro de mineração ao construir o dataset.
- [**radon**](https://github.com/rubik/radon) — métricas adicionais para código Python (Halstead, Maintainability Index).
- [**Pylint**](https://github.com/pylint-dev/pylint) — gerador de *silver labels* na fase de bootstrap do dataset.
- [**tree-sitter**](https://github.com/tree-sitter/tree-sitter) — fallback para parsing genérico se necessário.

### Refatoração mecânica (baseline B3)

- [**Rope**](https://github.com/python-rope/rope) — biblioteca de refactoring para Python, usada como **baseline B3** comparativo. Implementa Extract Method, Introduce Parameter, Rename, entre outros — também útil como gerador de *silver labels* na construção do dataset.

### Modelo base e fine-tuning

- [**HuggingFace Transformers**](https://github.com/huggingface/transformers) — carregamento e inferência dos modelos pré-treinados.
- [**HuggingFace PEFT**](https://github.com/huggingface/peft) — implementação de adaptadores LoRA.
- [**HuggingFace TRL**](https://github.com/huggingface/trl) — pipeline de fine-tuning supervisionado.
- [**Qwen2.5-Coder-1.5B**](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B) ou [**CodeT5-base**](https://huggingface.co/Salesforce/codet5-base) — modelo base candidato para geração de código (LoRAs).
- [**CodeBERT**](https://huggingface.co/microsoft/codebert-base) ou [**GraphCodeBERT**](https://huggingface.co/microsoft/graphcodebert-base) — encoder para o classificador multilabel (embeddings + cabeça densa com saída sigmoide por classe).

### Interface de linha de comando

- [**Typer**](https://github.com/fastapi/typer) — definição declarativa da CLI (escolha principal).
- [**Rich**](https://github.com/Textualize/rich) — formatação de saída no terminal, com renderização nativa da árvore hierárquica de resultados e exibição de diffs.

### Avaliação

- [**pytest**](https://github.com/pytest-dev/pytest) — execução dos testes do repositório-alvo sobre o código refatorado (avaliação *execution-based*).
- [**scikit-learn**](https://scikit-learn.org) — métricas do classificador (precision, recall, F1, macro-F1) e baselines.
- [**pandas**](https://pandas.pydata.org) — agregação dos resultados experimentais.

### Reprodutibilidade e ambiente

- **Docker** — empacotamento do ambiente de execução.
- **Make** — automação da pipeline (`make all` reproduz tabelas e figuras do relatório).
- **Google Colab** ou **Kaggle Notebooks** — ambiente de treinamento (GPU gratuita, 16 GB).

### Origem dos dados

A coleta combina **Git local** (via PyDriller, sem rate limit, foco em diffs e mensagens de commit que mencionam refatoração) e **GitHub API** (via PyGithub, para enriquecer o dataset com informações de issues e PRs ligadas a commits de refatoração). Repositórios-alvo serão selecionados via [**Seart GitHub Search (GHS)**](https://seart-ghs.si.usi.ch) com filtros de popularidade, atividade e linguagem (Python).

Datasets públicos como **MLCQ** (Madeyski & Lewowski, 2020) podem servir como *ground truth* complementar para validação cruzada do classificador, mediante adaptação cross-language (Java→Python).

---

*Engenharia de Software II — UFMG — 2026*
