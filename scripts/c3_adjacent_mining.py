"""C3 adjacent mining (Dia 3 do sprint).

Lê o catálogo PyRef em `data/test/oracle_pyref_test.jsonl`, agrupa por repo,
roda `mine_specific_commits()` em cada repo passando as listas de hashes
encontrados no catálogo, marca os pares resultantes com `source="adjacent_oracle"`
e mescla em `data/raw/`.

Uso:
    python3 scripts/c3_adjacent_mining.py
    python3 scripts/c3_adjacent_mining.py --oracle data/test/oracle_pyref_test.jsonl --out data/raw

Por design, este script **não** filtra por keyword na mensagem do commit
(os commits do PyRef já são refatorações validadas; o filtro de keyword
do `mine()` é apenas pré-filtro de recall para mineração cega).

Time-box: cada repo recebe um clone temporário (em `/tmp/c3_adjacent_clones/`)
reaproveitável entre execuções via `clone_repo_to`.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Permite rodar `python3 scripts/c3_adjacent_mining.py` da raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extracao.mineracao.minerador import mine_specific_commits  # noqa: E402


def load_oracle(path: Path) -> dict[str, list[str]]:
    """Retorna `{repo: [unique commit hashes]}` lidos do catálogo de oracle."""
    by_repo: dict[str, set[str]] = defaultdict(set)
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            repo = rec.get("repo")
            commit = rec.get("commit_hash")
            if repo and commit:
                by_repo[repo].add(commit)
    return {repo: sorted(commits) for repo, commits in by_repo.items()}


def run(oracle_path: Path, out_dir: Path, clones_dir: Path,
        partial_threshold: float = 0.1) -> dict:
    by_repo = load_oracle(oracle_path)
    print(f"Lidas {sum(len(v) for v in by_repo.values())} entradas em "
          f"{len(by_repo)} repos a partir de {oracle_path}.")
    clones_dir.mkdir(parents=True, exist_ok=True)

    grand_counts: dict[str, int] = defaultdict(int)
    repo_summary: list[tuple[str, int, dict, float]] = []

    for i, (repo, commits) in enumerate(by_repo.items(), 1):
        t0 = time.monotonic()
        print(f"\n[{i}/{len(by_repo)}] {repo}  ({len(commits)} commits)")
        try:
            counts = mine_specific_commits(
                repo_url=repo,
                output_path=out_dir,
                commit_hashes=commits,
                partial_threshold=partial_threshold,
                source="adjacent_oracle",
                clone_repo_to=str(clones_dir),
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  ERRO: {type(exc).__name__}: {exc}  ({elapsed:.1f}s)")
            repo_summary.append((repo, len(commits), {"_error": str(exc)}, elapsed))
            continue
        elapsed = time.monotonic() - t0
        for s, n in counts.items():
            grand_counts[s] += n
        total = sum(counts.values())
        per = "  ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(nenhum par)"
        print(f"  OK {total} pares em {elapsed:.1f}s — {per}")
        repo_summary.append((repo, len(commits), counts, elapsed))

    print("\n=== Resumo ===")
    for repo, n_commits, counts, secs in repo_summary:
        head = f"{repo}  ({n_commits} commits, {secs:.1f}s)"
        if "_error" in counts:
            print(f"  ERRO  {head}: {counts['_error']}")
        else:
            per = "  ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(nenhum par)"
            print(f"  {head}\n    {per}")
    print("\nTotal global por smell:")
    for s, n in sorted(grand_counts.items()):
        print(f"  {s}: {n}")
    print(f"  TOTAL: {sum(grand_counts.values())}")
    return dict(grand_counts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracle", type=Path,
                        default=Path("data/test/oracle_pyref_test.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("data/raw"),
                        help="diretório de saída (jsonls de pares)")
    parser.add_argument("--clones-dir", type=Path,
                        default=Path("/tmp/c3_adjacent_clones"),
                        help="diretório de cache para os git clones do PyDriller")
    parser.add_argument("--partial-threshold", type=float, default=0.1,
                        help="threshold permissivo (E1) — default 0.1")
    args = parser.parse_args()

    if not args.oracle.exists():
        print(f"ERRO: catálogo {args.oracle} não existe — rode primeiro o Dia 2",
              file=sys.stderr)
        return 1

    run(args.oracle, args.out, args.clones_dir,
        partial_threshold=args.partial_threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
