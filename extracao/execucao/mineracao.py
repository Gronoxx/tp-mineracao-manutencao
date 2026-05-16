# script de entrada: smells/mining/run_mining.py
from datetime import datetime
from pathlib import Path
from ..mineracao.minerador import mine

"""
Extrai os commits dos repositorios passados

Uso:
    python -m extracao.execucao.mineracao
    python -m extracao.execucao.mineracao --smell long_method --limit 20
"""

REPOS = ["https://github.com/pallets/flask"]

for repo in REPOS:
    print(f"Mining {repo}...")
    mine(
        repo_url=repo,
        output_path=Path("data/raw"),
        since=datetime(2020, 1, 1),
        to=datetime(2024, 12, 31),
    )