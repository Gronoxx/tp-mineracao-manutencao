"""Runner da mineração de pares de refatoração — corrida de produção.

Uso:
    python -m extracao.execucao.mineracao

Minera cada repositório de REPOS e mescla `<smell>.jsonl` em `data/raw/` (F1
do PR #11 — acumulativo, dedup por id). Em seguida, use
`extracao.execucao.visualizacao` para inspecionar e `filtro_smells` para curar.

Configuração de produção (Plano 3):
- Cap por smell baseado no "max útil" do agente de literatura LoRA.
- E1 ligado (`partial_threshold=0.1` — PR #18): aceita pares com redução de
  magnitude ≥ 10% (marcados `partial=True`), além dos pares estritos.
- Resiliência: um repo morto não derruba a corrida — try/except + log.
"""
import time
import traceback
from datetime import datetime
from pathlib import Path

from ..mineracao.minerador import mine

# Lista de repositórios maduros (>5k stars, >5 anos, com CI/testes).
REPOS = [
    # ── núcleo original (Plano 1, §6 do ESCOPO) ─────────────────────────────
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
    # ── expansão Plano 3 (20 repos maduros adicionais) ──────────────────────
    "https://github.com/celery/celery",
    "https://github.com/sqlalchemy/sqlalchemy",
    "https://github.com/tornadoweb/tornado",
    "https://github.com/aio-libs/aiohttp",
    "https://github.com/scrapy/scrapy",
    "https://github.com/matplotlib/matplotlib",
    "https://github.com/scipy/scipy",
    "https://github.com/statsmodels/statsmodels",
    "https://github.com/dask/dask",
    "https://github.com/networkx/networkx",
    "https://github.com/huggingface/transformers",
    "https://github.com/explosion/spaCy",
    "https://github.com/nltk/nltk",
    "https://github.com/ansible/ansible",
    "https://github.com/urllib3/urllib3",
    "https://github.com/pyca/cryptography",
    "https://github.com/pallets/werkzeug",
    "https://github.com/pallets/jinja",
    "https://github.com/pallets/click",
    "https://github.com/HypothesisWorks/hypothesis",
]

# Intervalo de tempo da mineração.
SINCE = datetime(2020, 1, 1)
TO = datetime(2024, 12, 31)

OUTPUT = Path("data/raw")

# Cap por smell — recalibrado com o "max útil" das recomendações de literatura
# do agente de pesquisa (Qwen2.5-Coder-1.5B + LoRA r=16, 5 adapters).  Cap é
# parada, não alvo: yield natural provavelmente ficará abaixo; isto evita
# desperdiçar curadoria humana se algum smell render bem demais.
CAP_POR_SMELL = {
    "R1": 4000,  # Extract Method
    "R2": 3500,  # Parameter Object
    "R3": 1500,  # Named Constant
    "R4": 2500,  # Guard Clauses
    "R5": 2000,  # Remove Dead Code
}
SMELLS = tuple(CAP_POR_SMELL)

# Verificação permissiva E1 (PR #18): aceita também pares com redução de
# magnitude >= 10%, marcados `partial=True`. Calibrado empiricamente.
PARTIAL_THRESHOLD = 0.1

THRESHOLDS = {
    "deep_nesting": 4,
    "long_param_list": 6,
    "long_method": {"lines": 40, "ccn": 12}
}

def _orcamento_repo(total: dict[str, int], repos_restantes: int,
                    cap: dict[str, int] = CAP_POR_SMELL) -> dict[str, int]:
    """Orçamento de pares por smell para o próximo repositório.

    Distribui o teto restante de CADA smell igualmente entre os repositórios
    ainda não minerados: nenhum repo enche o cap sozinho, então os pares vêm
    distribuídos por vários repos (diversidade de proveniência). Adaptativo —
    se os repos anteriores renderam pouco, o orçamento dos próximos cresce."""
    repos_restantes = max(1, repos_restantes)
    orcamento: dict[str, int] = {}
    for s in SMELLS:
        restante = max(0, cap[s] - total.get(s, 0))
        orcamento[s] = -(-restante // repos_restantes)  # divisão para cima
    return orcamento


def main() -> None:
    print(f"=== Mine de produção — {len(REPOS)} repos, "
          f"janela {SINCE.date()}–{TO.date()} ===")
    print(f"Caps: {CAP_POR_SMELL}")
    print(f"E1 partial_threshold = {PARTIAL_THRESHOLD}\n", flush=True)

    total: dict[str, int] = {s: 0 for s in SMELLS}
    falhas: list[tuple[str, str]] = []
    t_inicio = time.time()

    for i, repo in enumerate(REPOS):
        if all(total[s] >= CAP_POR_SMELL[s] for s in SMELLS):
            print(f"\nTodos os smells atingiram o cap — encerrando "
                  f"({i}/{len(REPOS)} repos minerados).")
            break

        caps = _orcamento_repo(total, repos_restantes=len(REPOS) - i)
        nome = repo.rsplit("/", 1)[-1]
        ti = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] [{i+1}/{len(REPOS)}] {nome} "
              f"(orçamento {caps}) ...", flush=True)

        try:
            counts = mine(repo_url=repo, output_path=OUTPUT,
                          since=SINCE, to=TO, caps=caps,
                          partial_threshold=PARTIAL_THRESHOLD,
                          threshold=THRESHOLDS)
        except Exception as exc:  # repo morto, clone falhou, etc.
            print(f"  !! FALHA em {nome}: {type(exc).__name__}: {exc}",
                  flush=True)
            traceback.print_exc()
            falhas.append((nome, f"{type(exc).__name__}: {exc}"))
            continue

        for smell, n in counts.items():
            total[smell] = total.get(smell, 0) + n
        print(f"  -> {counts}  ({time.time()-ti:.0f}s)  | acumulado {total}",
              flush=True)

    dur = time.time() - t_inicio
    print(f"\n=== Fim ({dur/60:.1f} min) ===")
    print(f"Total por smell: {total}")
    print(f"Caps por smell  : {CAP_POR_SMELL}")
    if falhas:
        print(f"\n{len(falhas)} repos falharam:")
        for nome, msg in falhas:
            print(f"  - {nome}: {msg}")
    print(f"\nPares escritos em {OUTPUT}/")


if __name__ == "__main__":
    main()
