"""C2 mass PR mining (Dia 11 do sprint).

Lê o cache de PRs em `data/pr_list.json` (produzido por
`extracao/execucao/pr_search.py`), agrupa por repo, e roda `mine_pr()` em
cada repo passando a lista de merge commit SHAs do PR. Os pares resultantes
recebem `source="mined_pr"` automaticamente.

Uso:
    python3 scripts/c2_mass_mine_pr.py
    python3 scripts/c2_mass_mine_pr.py --input data/pr_list.json --out data/raw
    python3 scripts/c2_mass_mine_pr.py --limit-repos 5   # smoke mode

Por design, este script **não** filtra por keyword na mensagem do commit
(os PRs já foram rotulados como refactor/cleanup/tech-debt pelo label
externo; a função keyword do `mine()` é pré-filtro de recall para
mineração cega, não faz sentido aqui).

Espelha o padrão de `scripts/c3_adjacent_mining.py` (Dia 3) trocando
oracle JSONL por PR list JSON e `mine_specific_commits` por `mine_pr`.
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Permite rodar `python3 scripts/c2_mass_mine_pr.py` da raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extracao.mineracao.minerador import mine_pr  # noqa: E402


def load_pr_list(path: Path) -> dict[str, list[str]]:
    """Retorna `{repo_name_with_owner: [merge_commit_shas]}` a partir do cache."""
    by_repo: dict[str, set[str]] = defaultdict(set)
    with path.open(encoding="utf-8") as f:
        entries = json.load(f)
    for rec in entries:
        repo = rec.get("repo")
        sha = rec.get("merge_commit_sha")
        if repo and sha:
            by_repo[repo].add(sha)
    return {repo: sorted(shas) for repo, shas in by_repo.items()}


def run(input_path: Path, out_dir: Path, clones_dir: Path,
        partial_threshold: float = 0.1,
        limit_repos: int | None = None) -> dict:
    by_repo = load_pr_list(input_path)
    total_prs = sum(len(v) for v in by_repo.values())
    print(f"Lidos {total_prs} PRs em {len(by_repo)} repos a partir de {input_path}.")
    if limit_repos is not None and limit_repos < len(by_repo):
        repos_kept = list(by_repo.keys())[:limit_repos]
        by_repo = {r: by_repo[r] for r in repos_kept}
        print(f"  --limit-repos={limit_repos}: processando {len(by_repo)} repos.")
    clones_dir.mkdir(parents=True, exist_ok=True)

    grand_counts: dict[str, int] = defaultdict(int)
    repo_summary: list[tuple[str, int, dict, float]] = []

    for i, (repo, shas) in enumerate(by_repo.items(), 1):
        t0 = time.monotonic()
        print(f"\n[{i}/{len(by_repo)}] {repo}  ({len(shas)} PRs)")
        repo_url = f"https://github.com/{repo}"
        try:
            counts = mine_pr(
                repo_url=repo_url,
                output_path=out_dir,
                merge_commit_shas=shas,
                partial_threshold=partial_threshold,
                clone_repo_to=str(clones_dir),
            )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  ERRO: {type(exc).__name__}: {exc}  ({elapsed:.1f}s)")
            repo_summary.append((repo, len(shas), {"_error": str(exc)}, elapsed))
            continue
        elapsed = time.monotonic() - t0
        for s, n in counts.items():
            grand_counts[s] += n
        total = sum(counts.values())
        per = "  ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(nenhum par)"
        print(f"  OK {total} pares em {elapsed:.1f}s — {per}")
        repo_summary.append((repo, len(shas), counts, elapsed))

    print("\n=== Resumo ===")
    n_errors = 0
    for repo, n_prs, counts, secs in repo_summary:
        head = f"{repo}  ({n_prs} PRs, {secs:.1f}s)"
        if "_error" in counts:
            print(f"  ERRO  {head}: {counts['_error']}")
            n_errors += 1
        else:
            per = "  ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "(nenhum par)"
            print(f"  {head}\n    {per}")
    print(f"\nTotal global por smell ({len(repo_summary) - n_errors} repos OK, "
          f"{n_errors} com erro):")
    for s, n in sorted(grand_counts.items()):
        print(f"  {s}: {n}")
    print(f"  TOTAL: {sum(grand_counts.values())}")
    return dict(grand_counts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path("data/pr_list.json"),
                        help="cache de PRs produzido por pr_search.py")
    parser.add_argument("--out", type=Path, default=Path("data/raw"),
                        help="diretório de saída (jsonls de pares)")
    parser.add_argument("--clones-dir", type=Path,
                        default=Path("/tmp/c2_pr_clones"),
                        help="diretório de cache para os git clones do PyDriller")
    parser.add_argument("--partial-threshold", type=float, default=0.1,
                        help="threshold permissivo (E1) — default 0.1")
    parser.add_argument("--limit-repos", type=int, default=None,
                        help="smoke mode: processa só primeiros N repos")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERRO: cache {args.input} não existe — rode primeiro pr_search.py",
              file=sys.stderr)
        return 1

    run(args.input, args.out, args.clones_dir,
        partial_threshold=args.partial_threshold,
        limit_repos=args.limit_repos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
