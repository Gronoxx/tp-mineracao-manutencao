# PySniff — Detector de Code Smells em Python por Mineração e Análise Estática

Ferramenta de linha de comando da disciplina **Engenharia de Software II** — UFMG.

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
ferramenta aponta para um arquivo ou diretório Python e reporta, por
função/método, os smells encontrados, com a **evidência métrica** que justifica
cada detecção.

O detector é apoiado por um pipeline de **mineração de repositórios** (`extracao/`):
a partir do histórico de commits do GitHub, extraem-se pares reais de refatoração
(antes→depois) que sustentam a calibração dos critérios de detecção e alimentam a
trilha futura de fine-tuning de um modelo de refatoração.

> **Escopo executado:** a proposta inicial previa 12 smells e 11 LoRAs. O escopo
> entregue — justificado em `docs/DECISOES_PROJETO.md` — é de **5 smells com
> detecção por regras estáticas** (a CLI deste repositório), com a trilha de
> fine-tuning condicionada à qualidade medida do dataset minerado.

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

## Tecnologias Utilizadas

- **CLI:** [Click](https://click.palletsprojects.com) (definição dos comandos) +
  [Rich](https://github.com/Textualize/rich) (árvore e tabelas no terminal).
- **Análise estática:** `ast` (stdlib), [Lizard](https://github.com/terryyin/lizard)
  (complexidade ciclomática e LOC).
- **Mineração de repositórios:** [PyDriller](https://github.com/ishepard/pydriller),
  GitPython, PyGithub; Seart GHS para seleção de repositórios.
- **Dataset/juiz:** Gemma (juiz LLM local) e proxy de qualidade por padrão AST.
- **Testes:** [pytest](https://github.com/pytest-dev/pytest) — mais de 250 testes
  cobrindo detectores, CLI e pipeline de mineração.
- **CI:** GitHub Actions (executa a suíte em Linux, macOS e Windows).
- **Trilha de fine-tuning (em desenvolvimento, `trilha_b/`):** HuggingFace
  Transformers + PEFT (QLoRA).

---

## Como Instalar

Requer **Python 3.11+**.

```bash
# 1. clone o repositório
git clone https://github.com/FilipeTerra/tp-mineracao-manutencao.git
cd tp-mineracao-manutencao

# 2. crie e ative um ambiente virtual
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate

# 3. instale as dependências da ferramenta
pip install -r requirements_cli.txt
```

> Para usar **apenas a CLI de detecção** (sem o pipeline de mineração), basta o
> conjunto mínimo: `pip install lizard click rich`.

---

## Como Utilizar

A ferramenta tem dois comandos: `scan` (analisar código) e `smells` (listar o
que é detectado).

```bash
# versão da ferramenta
python3 cli.py --version

# listar os 5 smells suportados
python3 cli.py smells

# analisar um arquivo ou diretório (árvore por arquivo → função → smell)
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

Os testes também são executados **automaticamente a cada push e pull request**
via GitHub Actions — veja [`.github/workflows/python-app.yaml`](.github/workflows/python-app.yaml).

---

## Pipeline de Mineração e Dataset

- `extracao/` minera pares de refatoração de repositórios Git (PyDriller): modos
  commit, PR, cross-file e rename, com validação por similaridade AST e checagem
  comportamental heurística.
- **Ancoragem em rule-ID de linter** (achado central do projeto): minerar commits
  que *removem* um aviso específico de linter (ex.: Pylint R0913, Ruff PLR2004)
  multiplica o yield de pares válidos em 5–25× vs. heurísticas de mensagem de
  commit. Detalhes em `docs/DECISOES_PROJETO.md`.
- **Oracle firewall:** PyRef e Sourcery são reservados para avaliação — nunca
  geram dados de treino; o split treino/teste é por repositório.

---

## Estrutura do Repositório

```
cli.py            CLI de detecção (produto do enunciado: comandos scan e smells)
detectores/       os 5 detectores estáticos (detect(fn) -> DetectionResult)
extracao/         mineração de pares de refatoração via PyDriller
core/             tipos compartilhados, schema e oráculo de avaliação
trilha_b/         configuração e scripts de fine-tuning (QLoRA; não treinado)
docs/             enunciado, decisões de projeto e checkpoints
tests/            suíte pytest (rodar da raiz: python3 -m pytest)
.github/workflows GitHub Actions (CI)
```

O projeto usa repositórios auxiliares separados por papel: `tp-es2-anotador`
(ferramenta web de anotação + codebook, público) e `tp-es2-dataset` (dados
minerados e anotações, privado).

---

*Engenharia de Software II — UFMG — 2026*
