# TP — Mineração de Repositórios: Detecção e Correção de Problemas de Manutenção em Código Python

Trabalho Prático da disciplina **Engenharia de Software II** — UFMG.

---

## 1. Membros do Grupo

- Gustavo Dias Apolinário
- Bernardo Vale dos Santos Bento
- Filipe Mauro da Terra Caldeira

---

## 2. Sobre o Sistema

Ferramenta de linha de comando (CLI) que **identifica problemas de manutenção em código Python e sugere correções automaticamente**, a partir da mineração de repositórios Git/GitHub. Diferente de abordagens tradicionais que apenas reportam métricas (LOC, complexidade, churn), o sistema atua em duas etapas neurais conectadas por um mecanismo de roteamento:

1. **Classificador leve** — recebe um trecho de código e prevê a qual das cinco classes de problema de manutenção ele pertence (ou se está livre de problemas dessa categoria).
2. **Adaptadores especializados (LoRA)** — uma vez identificada a classe, o sistema invoca o adaptador correspondente, treinado especificamente para corrigir aquele tipo de problema, e gera uma sugestão de patch.

### Classes de problemas atacadas

O sistema cobre cinco fatias bem definidas da taxonomia de manutenção de software (Swanson):

| # | Tipo de problema | Categoria (Swanson) |
|---|---|---|
| 1 | Remoção de código morto e imports não utilizados | Perfectiva |
| 2 | Refatoração de funções longas (extract method básico) | Perfectiva |
| 3 | Correção de erros de boundary (off-by-one, intervalos errados em `range()`) | Corretiva |
| 4 | Adição de None-checks ausentes antes de acessos | Preventiva |
| 5 | Adição de tratamento de exceções em I/O e parsing | Preventiva |

### Por que essa arquitetura

A escolha por roteamento com adaptadores LoRA (Low-Rank Adaptation) permite especialização sem o custo proibitivo de treinar e manter cinco modelos completos: todos os adaptadores compartilham o **mesmo modelo base** pré-treinado, e o roteador apenas troca qual adaptador está ativo durante a inferência. Cada adaptador pesa entre 5-50 MB e pode ser treinado em GPU gratuita (Google Colab / Kaggle).

### Pipeline de uso

1. Usuário aponta a CLI para um repositório Python (caminho local ou URL Git).
2. O sistema clona/atualiza o repositório e extrai trechos candidatos.
3. O classificador atribui uma classe a cada trecho (ou descarta).
4. O adaptador LoRA correspondente gera a sugestão de correção.
5. Saída: relatório com problemas detectados, classe, sugestão de patch e métricas de avaliação.

### Avaliação

A qualidade das correções será avaliada de forma **execution-based** (o código corrigido continua passando nos testes originais do repositório?), comparada contra três baselines:

- **B0:** modelo base sem fine-tuning, em modo zero-shot.
- **B1:** um único modelo fine-tunado com a união das cinco classes (multitask).
- **B2:** especialistas com roteamento perfeito (oracle) — limite superior do roteador.

---

## 3. Tecnologias Possíveis

A lista abaixo reúne as tecnologias candidatas para cada componente do sistema. A escolha final entre alternativas será feita ao longo da implementação, conforme as restrições práticas (custo computacional, qualidade do dataset gerado, integração).

### Mineração de repositórios

- [**PyDriller**](https://github.com/ishepard/pydriller) — framework Python para análise de repositórios Git; principal ferramenta para extração de pares (versão antes / versão depois do fix).
- [**GitPython**](https://github.com/gitpython-developers/GitPython) — biblioteca para operações Git de baixo nível (apoio).
- [**PyGithub**](https://github.com/PyGithub/PyGithub) — integração com a API do GitHub para coleta de issues, PRs e metadados que enriquecem o dataset.

### Modelo base e fine-tuning

- [**HuggingFace Transformers**](https://github.com/huggingface/transformers) — carregamento e inferência dos modelos pré-treinados.
- [**HuggingFace PEFT**](https://github.com/huggingface/peft) — implementação de adaptadores LoRA.
- [**HuggingFace TRL**](https://github.com/huggingface/trl) — pipeline de fine-tuning supervisionado.
- [**Qwen2.5-Coder-1.5B**](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B) ou [**CodeT5-base**](https://huggingface.co/Salesforce/codet5-base) — modelo base candidato para geração de código.
- [**CodeBERT**](https://huggingface.co/microsoft/codebert-base) — embeddings de entrada para o classificador leve.

### Análise estática e parsing

- [**Lizard**](https://github.com/terryyin/lizard) — métricas de complexidade ciclomática multi-linguagem.
- [**ast (stdlib do Python)**](https://docs.python.org/3/library/ast.html) — análise sintática nativa para extração de features.
- [**tree-sitter**](https://github.com/tree-sitter/tree-sitter) — fallback para parsing genérico se necessário.
- [**radon**](https://github.com/rubik/radon) — métricas adicionais para código Python.

### Interface de linha de comando

- [**Typer**](https://github.com/fastapi/typer) — definição declarativa da CLI (escolha principal).
- [**Rich**](https://github.com/Textualize/rich) — formatação de saída no terminal (tabelas, cores, progresso).

### Avaliação

- [**pytest**](https://github.com/pytest-dev/pytest) — execução dos testes do repositório-alvo sobre o código corrigido (avaliação execution-based).
- [**scikit-learn**](https://scikit-learn.org) — métricas do classificador (precision, recall, F1) e baselines.
- [**pandas**](https://pandas.pydata.org) — agregação dos resultados experimentais.

### Reprodutibilidade e ambiente

- **Docker** — empacotamento do ambiente de execução.
- **Make** — automação da pipeline (`make all` reproduz tabelas e figuras do relatório).
- **Google Colab** ou **Kaggle Notebooks** — ambiente de treinamento (GPU gratuita, 16 GB).

### Origem dos dados

A coleta combina **Git local** (via PyDriller, sem rate limit, foco em diffs e mensagens de commit) e **GitHub API** (via PyGithub, para enriquecer o dataset com informações de issues e PRs ligadas a commits de fix). Repositórios-alvo serão selecionados via [**Seart GitHub Search (GHS)**](https://seart-ghs.si.usi.ch) com filtros de popularidade, atividade e linguagem (Python).

---

*Engenharia de Software II — UFMG — 2026*
