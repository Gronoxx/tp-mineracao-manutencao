# PySniff — Detecção e Refatoração de Code Smells em Python via Mineração de Repositórios

Trabalho Prático da disciplina **Engenharia de Software II** — UFMG.

---

## Membros do Grupo

- Gustavo Dias Apolinário
- Bernardo Vale dos Santos Bento
- Filipe Mauro da Terra Caldeira

---

## Objetivo da Ferramenta

**PySniff** é uma ferramenta de linha de comando que ataca um problema de
**manutenção e evolução de software**: a presença de *code smells* — estruturas
de código que funcionam, mas dificultam manutenção, leitura e evolução. A
ferramenta **identifica 5 code smells em código Python por análise estática**,
e é construída sobre um pipeline de **mineração de repositórios** que extrai
pares reais de refatoração (antes→depois) do histórico de commits do GitHub.

O projeto tem **duas entregas complementares**:

1. **A CLI de detecção** (`cli.py`) — produto do enunciado: aponta-se para um
   arquivo ou diretório Python e ela reporta, por função/método, os smells
   encontrados com a evidência métrica de cada um.
2. **O dataset minerado com qualidade medida** (repo privado `tp-es2-dataset`) —
   pares before→after por smell, validados por juiz LLM (Gemma) e auditados por
   **sonda de qualidade humana** (2 anotadores, amostra estratificada, precisão
   reponderada por taxa-base, Cohen κ) — insumo para o **fine-tuning futuro de um
   modelo de refatoração** (Trilha B; alvo: Stable Code Instruct 3B + QLoRA),
   que proporá automaticamente as correções dos smells detectados.

> **Escopo real vs. proposta original:** a proposta inicial previa 12 smells e
> 11 LoRAs. O escopo executado — documentado com justificativas em
> `docs/DECISOES_PROJETO.md` — é de **5 smells com detecção por regras estáticas**
> (a CLI deste repositório) e a trilha de fine-tuning condicionada à qualidade
> medida do dataset (a sonda de qualidade veio antes do treino, deliberadamente:
> *garbage in, garbage out*). A **Trilha B (refatoração) será continuada em
> breve.**

### Os 5 smells cobertos

| ID | Smell | Refatoração-alvo | Critério de detecção |
|---|---|---|---|
| R1 | Long Method | Extract Method | Lizard (NLOC > 30 ou CCN > 10) |
| R2 | Long Parameter List | Parameter Object | contagem AST (> 5 parâmetros) |
| R3 | Magic Numbers | Named Constant | AST walk com whitelist de literais estruturais |
| R4 | Deep Nesting | Guard Clauses | profundidade AST (> 3) |
| R5 | Dead Code | Remoção | análise AST (inalcançável, dead stores) |

Cada detector expõe o contrato `detect(fn: FunctionInfo) -> DetectionResult` (`detectores/`).

---

## Como Instalar

Requer **Python 3.11+** (testado em CI com 3.13 em Linux, macOS e Windows).

```bash
# 1. clone o repositório
git clone https://github.com/Gronoxx/tp-mineracao-manutencao
cd tp-mineracao-manutencao

# 2. crie e ative um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. instale as dependências da ferramenta
pip install -r requirements_cli.txt
```

> Para usar **apenas a CLI de detecção** (sem o pipeline de mineração), o
> conjunto mínimo de dependências é: `pip install lizard click rich`.

---

## Como Utilizar

A ferramenta tem dois comandos: `scan` (analisar código) e `smells` (listar o
que é detectado).

```bash
# versão da ferramenta
python3 cli.py --version

# listar os 5 smells suportados
python3 cli.py smells

# analisar um arquivo ou diretório (árvore Rich por arquivo → função → smell)
python3 cli.py scan caminho/do/projeto/

# restringir a smells específicos — por ID (R1–R5) ou nome
python3 cli.py scan src/ --smell R1 --smell dead_code

# saída JSON estruturada (para integração/scripts)
python3 cli.py scan src/ --json > resultado.json

# uso em CI: retorna código de saída 1 se algum smell for detectado
python3 cli.py scan src/ --fail-on-detect
```

**Códigos de saída do `scan`:** `0` análise concluída · `1` `--fail-on-detect`
ativo e houve detecção · `2` nenhum arquivo `.py` encontrado. Veja
`python3 cli.py scan --help` para todos os detalhes.

---

## Como Executar os Testes Localmente

```bash
# instale as dependências de teste (além das da ferramenta)
pip install -r requirements_cli.txt -r requirements-dev.txt

# rode a suíte completa a partir da raiz do repositório
python3 -m pytest

# com relatório de cobertura
python3 -m pytest --cov
```

A suíte tem **mais de 250 testes** (detectores, CLI e pipeline de mineração) e é
executada **automaticamente a cada push e pull request** via GitHub Actions —
veja [`.github/workflows/python-app.yaml`](.github/workflows/python-app.yaml).

---

## Pipeline de Mineração e Dataset

- `extracao/` minera pares de refatoração de repositórios Git (PyDriller): modos
  commit, PR, cross-file e rename, com validação por similaridade AST e checagem
  comportamental heurística.
- **Ancoragem em rule-ID de linter** (achado central do projeto): minerar commits
  que *removem* um aviso específico de linter (ex.: Pylint R0913, Ruff PLR2004)
  multiplica o yield de pares válidos em 5–25× vs. heurísticas de mensagem de
  commit — o yield é proporcional à **objetividade do critério** do smell.
  Detalhes e números em `docs/DECISOES_PROJETO.md`.
- 5.072 candidatos minerados → 616 pares aprovados pelo juiz LLM (Gemma) →
  **sonda de qualidade humana de 50 pares** (estratificada, cega ao proxy AST,
  precisão populacional reponderada por taxa-base, κ) + re-auditoria assistida
  por LLM. Resultados, codebook de anotação e decisão de curadoria vivem em
  `tp-es2-dataset` e `tp-es2-anotador/CODEBOOK.md`.
- **Oracle firewall:** PyRef e Sourcery são reservados para avaliação — nunca
  geram dados de treino; o split treino/teste é por repositório.

### Trilha B — Fine-tuning de refatoração (em desenvolvimento)

O dataset minerado e auditado alimenta a **Trilha B**: o treino de um modelo que
proporá automaticamente a correção dos smells detectados. A infraestrutura vive
em `trilha_b/` (configuração e scripts de fine-tuning com QLoRA; alvo
**Stable Code Instruct 3B**). O modelo ainda não foi treinado — esta trilha será
continuada em breve.

---

## Tecnologias Utilizadas

- **CLI:** [Click](https://click.palletsprojects.com) (definição dos comandos) +
  [Rich](https://github.com/Textualize/rich) (árvore e tabelas no terminal).
- **Análise estática:** `ast` (stdlib), [Lizard](https://github.com/terryyin/lizard),
  Pylint, Ruff, Vulture.
- **Mineração:** PyDriller, GitPython, PyGithub (issues/PRs), Seart GHS para
  seleção de repositórios.
- **Dataset/juiz:** Gemma (juiz LLM local), proxy de qualidade por padrão AST
  (`estimate_positive_quality.py`), anotador web próprio (`tp-es2-anotador`).
- **Testes:** [pytest](https://github.com/pytest-dev/pytest) — mais de 250 testes
  cobrindo detectores, CLI e pipeline de mineração.
- **CI:** GitHub Actions (executa a suíte em Linux, macOS e Windows).
- **Trilha de fine-tuning (em desenvolvimento, `trilha_b/`):** HuggingFace
  Transformers + PEFT (QLoRA), alvo Stable Code Instruct 3B.

---

## Estrutura do Repositório

O projeto usa três repositórios, separados por papel:

| Repositório | Papel | Visibilidade |
|---|---|---|
| **`tp-mineracao-manutencao`** (este) | código: mineração, detectores, CLI, trilha de treino | público |
| `tp-es2-anotador` | ferramenta web de anotação + codebook + scorer da sonda | público |
| `tp-es2-dataset` | dados: candidatos minerados, veredictos, anotações, sonda | privado |

Layout do código:

- `cli.py` — CLI de detecção (produto do enunciado: comandos `scan` e `smells`).
- `detectores/` — os 5 detectores estáticos (`detect(fn) -> DetectionResult`).
- `extracao/` — mineração de pares de refatoração via PyDriller.
- `core/` — tipos compartilhados, schema e oráculo de avaliação.
- `trilha_b/` — configuração e scripts de fine-tuning (QLoRA; ainda não treinado).
- `gemma_judge_dataset.py`, `estimate_positive_quality.py` — juiz LLM e proxy de
  qualidade do dataset.
- `docs/` — enunciado, decisões de projeto datadas e checkpoints.
- `tests/` — suíte pytest (rodar da raiz: `python3 -m pytest`).
- `.github/workflows/` — GitHub Actions (CI).

---

*Engenharia de Software II — UFMG — 2026*
