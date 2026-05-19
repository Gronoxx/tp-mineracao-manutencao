"""Runner da mineração de pares de refatoração.

Uso:
    python -m extracao.execucao.mineracao

Minera cada repositório de REPOS e escreve `<smell>.jsonl` em `data/raw/`
(escrita idempotente — rodar de novo não duplica). Em seguida, use
`extracao.execucao.visualizacao` para inspecionar e `filtro_smells` para curar.
"""
from datetime import datetime
from pathlib import Path

from ..mineracao.minerador import mine

# Lista de repositórios (ESCOPO §6 — >1000 stars, ativos, com testes).
REPOS = [
    "https://github.com/django/django",
    "https://github.com/pallets/flask",
    "https://github.com/fastapi/fastapi",
    "https://github.com/psf/requests",
    "https://github.com/pandas-dev/pandas",
    "https://github.com/scikit-learn/scikit-learn",
    "https://github.com/numpy/numpy",
    "https://github.com/python-pillow/Pillow",
    "https://github.com/sphinx-doc/sphinx",
    "https://github.com/pytest-dev/pytest",
    "https://github.com/python-poetry/poetry",
    "https://github.com/psf/black",
    "https://github.com/python/mypy",
    "https://github.com/pydantic/pydantic",
    "https://github.com/encode/httpx",
    "https://github.com/sympy/sympy",
]

# Intervalo de tempo da mineração.
SINCE = datetime(2020, 1, 1)
TO = datetime(2024, 12, 31)

OUTPUT = Path("data/raw")


def main() -> None:
    total: dict[str, int] = {}
    for repo in REPOS:
        print(f"Minerando {repo} ...")
        counts = mine(repo_url=repo, output_path=OUTPUT, since=SINCE, to=TO)
        for smell, n in counts.items():
            total[smell] = total.get(smell, 0) + n
        print(f"  -> {counts}")
    print(f"\nTotal por smell: {total}")
    print(f"Pares escritos em {OUTPUT}/")


if __name__ == "__main__":
    main()
