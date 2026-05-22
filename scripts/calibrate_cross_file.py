"""Fase C-1 — Calibração G1+G2 do cross_file_threshold.

Roda `mine()` com `cross_file_threshold` variando em {0.5, 0.6, 0.7, 0.8, 0.9}
em 3 repos pequenos (flask, click, requests). Cada threshold escreve em
diretório próprio. Após a geração:

1. G1 — Conta pares cross_file por threshold (yield).
2. G2 — Roda behavioral_check em amostra de até 50 pares por threshold.
3. Reporta precision (taxa de equivalência entre pares COMPARÁVEIS) por
   threshold.
4. Recomenda o menor threshold com precision > 0.7 (critério do plano).

Janela usada: 2020-01-01 a 2024-12-31 (mesma do mass mine #1).
"""
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extracao.mineracao.minerador import mine  # noqa: E402
from extracao.mineracao.behavioral_check import behavioral_check  # noqa: E402

THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]
REPOS = [
    # Top yielders da Fase A — repos grandes com histórico de refator
    # cross-file. flask/click/requests (versão original) eram pequenos
    # demais para gerar universo de calibração (Issue #2).
    "https://github.com/numpy/numpy",
    "https://github.com/pandas-dev/pandas",
    "https://github.com/sympy/sympy",
    "https://github.com/scipy/scipy",
    "https://github.com/matplotlib/matplotlib",
]
SINCE = datetime(2020, 1, 1)
TO = datetime(2024, 12, 31)
SAMPLE_PER_THRESHOLD = 50
SEED = 42


def run_mine_per_threshold(base_dir: Path) -> dict[float, Path]:
    """Para cada threshold, roda mine() nos 3 repos. Retorna mapa threshold→dir."""
    out_paths: dict[float, Path] = {}
    for th in THRESHOLDS:
        out_dir = base_dir / f"th_{th:.1f}"
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== Threshold {th} ===")
        for i, repo in enumerate(REPOS, 1):
            ti = time.time()
            print(f"  [{i}/{len(REPOS)}] {repo.rsplit('/',1)[-1]} ...", flush=True)
            try:
                counts = mine(repo_url=repo, output_path=out_dir,
                              since=SINCE, to=TO,
                              cross_file_threshold=th)
                print(f"    -> {counts}  ({time.time()-ti:.0f}s)", flush=True)
            except Exception as exc:
                print(f"    !! FALHA: {type(exc).__name__}: {exc}", flush=True)
        out_paths[th] = out_dir
    return out_paths


def load_cross_file_pairs(out_dir: Path) -> list[dict]:
    """Carrega só pares com source='cross_file' do diretório."""
    import json
    pairs = []
    for f in out_dir.glob("*.jsonl"):
        with f.open() as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("source") == "cross_file":
                    pairs.append(rec)
    return pairs


def behavioral_precision(pairs: list[dict], sample_n: int) -> dict:
    """Behavioral check em amostra. Retorna stats."""
    if not pairs:
        return {"sampled": 0, "equiv": 0, "diff": 0, "inconclusive": 0,
                "precision": None}
    random.seed(SEED)
    sample = random.sample(pairs, min(sample_n, len(pairs)))
    equiv = diff = inconclusive = 0
    for p in sample:
        try:
            r = behavioral_check(p["before_code"], p["after_code"])
        except Exception:
            inconclusive += 1
            continue
        # BehavioralCheckResult: equivalent, n_samples, n_matching,
        # n_one_raised, n_different_output, error_msg
        if r.error_msg:
            inconclusive += 1
        elif r.n_samples == 0:
            inconclusive += 1
        elif r.equivalent:
            equiv += 1
        else:
            diff += 1
    comparable = equiv + diff
    precision = equiv / comparable if comparable else None
    return {
        "sampled": len(sample),
        "equiv": equiv,
        "diff": diff,
        "inconclusive": inconclusive,
        "precision": precision,
    }


def main() -> int:
    base_dir = Path("data/cross_file_calibration")
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Fase C-1 — Calibração cross_file ===")
    print(f"Thresholds: {THRESHOLDS}")
    print(f"Repos: {[r.rsplit('/',1)[-1] for r in REPOS]}")
    print(f"Janela: {SINCE.date()} a {TO.date()}")
    print(f"Sample size: {SAMPLE_PER_THRESHOLD}")

    out_paths = run_mine_per_threshold(base_dir)

    print("\n\n=== Resultados ===")
    print(f"{'Threshold':<11} {'Pairs cross_file':>17} {'sampled':>9} "
          f"{'equiv':>6} {'diff':>5} {'inconclusive':>13} {'precision':>10}")
    print("-" * 80)

    results = {}
    for th in THRESHOLDS:
        pairs = load_cross_file_pairs(out_paths[th])
        stats = behavioral_precision(pairs, SAMPLE_PER_THRESHOLD)
        results[th] = (len(pairs), stats)
        prec = f"{stats['precision']:.2f}" if stats["precision"] is not None else "—"
        print(f"{th:<11.1f} {len(pairs):>17} {stats['sampled']:>9} "
              f"{stats['equiv']:>6} {stats['diff']:>5} "
              f"{stats['inconclusive']:>13} {prec:>10}")

    # Recomendação: menor threshold com precision > 0.7
    print("\n=== Recomendação ===")
    chosen = None
    for th in THRESHOLDS:
        n_pairs, stats = results[th]
        p = stats["precision"]
        if p is not None and p > 0.7 and n_pairs > 0:
            chosen = th
            print(f"Menor threshold com precision > 0.7: {th} "
                  f"({n_pairs} pares, precision={p:.2f})")
            break
    if chosen is None:
        print("Nenhum threshold atinge precision > 0.7 com pares suficientes.")
        print("Sugestão: usar o MAIOR threshold disponível (0.9) — mais conservador.")
        chosen = max(t for t, (n, _) in results.items() if n > 0) if any(n > 0 for n, _ in results.values()) else None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
