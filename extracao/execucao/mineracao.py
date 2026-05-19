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

# Cap global por smell — alvo de um dataset de tamanho revisável (~300/smell,
# estimativa do ESCOPO P3). A mineração para de coletar um smell ao atingi-lo.
CAP_POR_SMELL = 300
SMELLS = ("R1", "R2", "R3", "R4", "R5")


def _orcamento_repo(total: dict[str, int], repos_restantes: int,
                    cap: int = CAP_POR_SMELL) -> dict[str, int]:
    """Orçamento de pares por smell para o próximo repositório.

    Distribui o cap restante de cada smell igualmente entre os repositórios
    ainda não minerados: nenhum repo enche o cap sozinho, então os ~300 pares
    vêm distribuídos por vários repos (diversidade de proveniência). É
    adaptativo — se os repos anteriores renderam pouco, o orçamento dos
    próximos cresce."""
    repos_restantes = max(1, repos_restantes)
    orcamento = {}
    for s in SMELLS:
        restante = max(0, cap - total.get(s, 0))
        orcamento[s] = -(-restante // repos_restantes)  # divisão para cima
    return orcamento


def main() -> None:
    total: dict[str, int] = {s: 0 for s in SMELLS}
    for i, repo in enumerate(REPOS):
        if all(total[s] >= CAP_POR_SMELL for s in SMELLS):
            print(f"Todos os smells atingiram o cap ({CAP_POR_SMELL}) — encerrando.")
            break
        caps = _orcamento_repo(total, repos_restantes=len(REPOS) - i)
        print(f"Minerando {repo} ... (orçamento/smell: {caps})")
        counts = mine(repo_url=repo, output_path=OUTPUT, since=SINCE, to=TO, caps=caps)
        for smell, n in counts.items():
            total[smell] = total.get(smell, 0) + n
        print(f"  -> {counts}  | acumulado: {total}")
    print(f"\nTotal por smell: {total}")
    print(f"Pares escritos em {OUTPUT}/  (cap {CAP_POR_SMELL}/smell)")


if __name__ == "__main__":
    main()
