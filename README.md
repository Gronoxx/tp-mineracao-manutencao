![pysniff-logo](./img/pysniff-logo.png)

*Versão em português: [README.pt-BR.md](README.pt-BR.md)*

# PySniff: code smell detection and refactoring dataset construction for Python

PySniff is a command line tool that detects five code smells in Python through static
analysis, built on top of a repository mining pipeline that extracts real before/after
refactoring pairs from GitHub commit history.

Course project for Software Engineering II at UFMG, developed by Gustavo Dias Apolinário,
Bernardo Vale dos Santos Bento and Filipe Mauro da Terra Caldeira.

## The main finding

Mining commits that **remove a specific linter rule** (Pylint R0913, Ruff PLR2004 and
others) yields 5 to 25 times more valid refactoring pairs than heuristics over commit
messages. The multiplier is not uniform: it scales with how objectively the smell can be
defined. A parameter count is unambiguous, so its yield is high. "Long method" depends on
thresholds, so its yield is low.

This shaped the whole pipeline. Numbers and reasoning are in `docs/DECISOES_PROJETO.md`.

## Dataset construction

The pipeline mined 5,072 candidate pairs. An LLM judge (Gemma, running locally) approved
616 of them. A human quality probe then audited a stratified sample of 50, blind to the AST
proxy, with population precision reweighted by base rate and inter annotator agreement
measured by Cohen's kappa. Two annotators, followed by an LLM assisted re audit.

Three decisions kept the dataset honest:

**Oracle firewall.** PyRef and Sourcery are reserved for evaluation and never produce
training data. A tool cannot be both the teacher and the exam.

**Repository level split.** Train and test never share a repository, so a model cannot
memorise one project's idioms and score well on itself.

**Quality probe before training.** The sample was audited before any fine tuning started,
deliberately. Measuring the data after training the model tells you nothing you can act on.

## The five smells

| ID | Smell | Target refactoring | Detection criterion |
|---|---|---|---|
| R1 | Long Method | Extract Method | Lizard, NLOC above 30 or cyclomatic complexity above 10 |
| R2 | Long Parameter List | Parameter Object | AST parameter count above 5 |
| R3 | Magic Numbers | Named Constant | AST walk with a whitelist of structural literals |
| R4 | Deep Nesting | Guard Clauses | AST depth above 3 |
| R5 | Dead Code | Removal | AST analysis for unreachable code and dead stores |

Every detector implements the same contract, `detect(fn: FunctionInfo) -> DetectionResult`,
in `detectores/`.

## Scope, stated plainly

The original proposal promised 12 smells and 11 LoRA adapters. What was built and documented
is 5 smells with rule based detection, plus a fine tuning track conditioned on the measured
quality of the dataset. The reduction is recorded with its reasoning in
`docs/DECISOES_PROJETO.md` rather than quietly dropped.

The refactoring model itself has not been trained. Its infrastructure lives in `trilha_b/`,
targeting Stable Code Instruct 3B with QLoRA.

## Installing

Requires Python 3.11 or later. Continuous integration runs the suite on Python 3.13 across
Linux, macOS and Windows.

```bash
git clone https://github.com/Gronoxx/PySniff
cd PySniff
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements_cli.txt
```

For the detection CLI alone, without the mining pipeline, the minimum is
`pip install lizard click rich`.

## Using it

```bash
python3 cli.py smells                          # list the five supported smells
python3 cli.py scan path/to/project/           # scan a file or directory
python3 cli.py scan src/ --smell R1            # restrict to specific smells
python3 cli.py scan src/ --json > result.json  # structured output
python3 cli.py scan src/ --fail-on-detect      # exit code 1 when a smell is found, for CI
```

Exit codes for `scan`: 0 when analysis completes, 1 when `--fail-on-detect` is set and
something was detected, 2 when no Python file was found.

## Tests

```bash
pip install -r requirements_cli.txt -r requirements-dev.txt
python3 -m pytest
python3 -m pytest --cov
```

Over 250 tests covering detectors, the CLI and the mining pipeline, run on every push and
pull request through GitHub Actions.

## Built with

Click and Rich for the command line. The standard library `ast` module, Lizard, Pylint, Ruff
and Vulture for static analysis. PyDriller, GitPython and PyGithub for mining, with Seart GHS
for repository selection. Gemma as a local LLM judge. pytest and GitHub Actions for testing.
HuggingFace Transformers and PEFT for the fine tuning track.

## Repository layout

The project spans three repositories, separated by role.

| Repository | Role | Visibility |
|---|---|---|
| `PySniff` (this one) | mining, detectors, CLI, training track | public |
| `PySniff-anotador` | web annotation tool, codebook and probe scorer | public |
| `PySniff-dataset` | mined candidates, verdicts, annotations, quality probe | private |

Inside this repository, `cli.py` holds the detection interface, `detectores/` the five static
detectors, `extracao/` the mining pipeline, `core/` shared types and the evaluation oracle,
`trilha_b/` the fine tuning configuration, and `docs/` the dated design decisions.
