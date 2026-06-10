# TP — Mineração de Repositórios: Detecção e Refatoração de Code Smells em Python

Trabalho Prático da disciplina **Engenharia de Software II** — UFMG.

---

## 1. Membros do Grupo

- Gustavo Dias Apolinário
- Bernardo Vale dos Santos Bento
- Filipe Mauro da Terra Caldeira

---

## 2. Sobre o Sistema

Ferramenta de linha de comando que **identifica 5 code smells em código Python por análise estática**, construída sobre um pipeline de **mineração de repositórios** que extrai pares reais de refatoração (antes→depois) do histórico de commits do GitHub. O projeto tem duas entregas complementares:

1. **A CLI de detecção** (`cli.py`) — produto do enunciado: aponta-se para um arquivo ou diretório Python e ela reporta, por função/método, os smells encontrados com a evidência métrica de cada um.
2. **O dataset minerado com qualidade medida** (repo privado `tp-es2-dataset`) — pares before→after por smell, validados por juiz LLM (Gemma) e auditados por **sonda de qualidade humana** (2 anotadores, amostra estratificada, precisão reponderada por taxa-base, Cohen κ) — insumo para o fine-tuning futuro de um modelo de refatoração (alvo: Stable Code Instruct 3B + QLoRA).

> **Escopo real vs. proposta original:** a proposta inicial previa 12 smells e 11 LoRAs. O escopo executado — documentado com justificativas em `docs/DECISOES_PROJETO.md` — é de **5 smells com detecção por regras estáticas** e a trilha de fine-tuning condicionada à qualidade medida do dataset (a sonda de qualidade veio antes do treino, deliberadamente: *garbage in, garbage out*).

### Os 5 smells cobertos

| ID | Smell | Refatoração-alvo | Detecção |
|---|---|---|---|
| R1 | Long Method | Extract Method | Lizard (NLOC > 30 ou CCN > 10) |
| R2 | Long Parameter List | Parameter Object | contagem AST (> 5 parâmetros) |
| R3 | Magic Numbers | Named Constant | AST walk com whitelist de literais estruturais |
| R4 | Deep Nesting | Guard Clauses | profundidade AST (> 3) |
| R5 | Dead Code | Remoção | análise AST (inalcançável, dead stores) |

Cada detector expõe o contrato `detect(fn: FunctionInfo) -> DetectionResult` (`detectores/`).

## 3. Como usar a CLI

```bash
pip install -r detectores/requirements.txt click rich

# listar os smells suportados
python3 cli.py smells

# analisar um arquivo ou diretório (árvore Rich por arquivo → função → smell)
python3 cli.py scan caminho/do/projeto/

# restringir smells, saída JSON, ou uso em CI
python3 cli.py scan src/ --smell long_method --smell dead_code
python3 cli.py scan src/ --json > resultado.json
python3 cli.py scan src/ --fail-on-detect   # exit 1 se detectar algo
```

## 4. Pipeline de mineração e dataset

- `extracao/` minera pares de refatoração de repositórios Git (PyDriller): modos commit, PR, cross-file e rename, com validação por similaridade AST e checagem comportamental heurística.
- **Ancoragem em rule-ID de linter** (achado central do projeto): minerar commits que *removem* um aviso específico de linter (ex.: Pylint R0913, Ruff PLR2004) multiplica o yield de pares válidos em 5–25× vs. heurísticas de mensagem de commit — o yield é proporcional à **objetividade do critério** do smell. Detalhes e números em `docs/DECISOES_PROJETO.md`.
- 5.072 candidatos minerados → 616 pares aprovados pelo juiz LLM (Gemma) → **sonda de qualidade humana de 50 pares** (estratificada, cega ao proxy AST, precisão populacional reponderada por taxa-base, κ) + re-auditoria assistida por LLM. Resultados, codebook de anotação e decisão de curadoria vivem em `tp-es2-dataset` e `tp-es2-anotador/CODEBOOK.md`.
- **Oracle firewall:** PyRef e Sourcery são reservados para avaliação — nunca geram dados de treino; split treino/teste é por repositório.

## 5. Tecnologias utilizadas

- **Mineração:** PyDriller, GitPython, PyGithub (issues/PRs), Seart GHS para seleção de repositórios.
- **Análise estática:** `ast` (stdlib), Lizard, Pylint, Ruff, Vulture.
- **CLI:** Click + Rich.
- **Dataset/juiz:** Gemma (juiz LLM local), proxy de qualidade por padrão AST (`estimate_positive_quality.py`), anotador web próprio (`tp-es2-anotador`).
- **Testes:** pytest (243 testes — pipeline de mineração, detectores e CLI).
- **Trilha de fine-tuning (em desenvolvimento, `trilha_b/`):** HuggingFace Transformers + PEFT (QLoRA), alvo Stable Code Instruct 3B.

## 6. Estrutura do repositório

O projeto usa três repositórios, separados por papel:

| Repositório | Papel | Visibilidade |
|---|---|---|
| **`tp-mineracao-manutencao`** (este) | código: mineração, detectores, CLI, trilha de treino | público |
| `tp-es2-anotador` | ferramenta web de anotação + codebook + scorer da sonda | público |
| `tp-es2-dataset` | dados: candidatos minerados, veredictos, anotações, sonda | privado |

Layout do código:

- `cli.py` — CLI de detecção (produto do enunciado).
- `detectores/` — os 5 detectores estáticos (`detect(fn) -> DetectionResult`).
- `extracao/` — mineração de pares de refatoração via PyDriller.
- `core/` — tipos compartilhados, schema e oráculo de avaliação.
- `trilha_b/` — configuração e scripts de fine-tuning (QLoRA; ainda não treinado).
- `gemma_judge_dataset.py`, `estimate_positive_quality.py` — juiz LLM e proxy de qualidade do dataset.
- `docs/` — enunciado, decisões de projeto datadas e checkpoints.
- `tests/` — suíte pytest (rodar da raiz: `python3 -m pytest`).

---

*Engenharia de Software II — UFMG — 2026*
