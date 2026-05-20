"""C2 — PR Search via GraphQL (Dia 10 do sprint).

Enumera PRs merged do GitHub que ostentam labels de refatoração e persiste
`(repo, pr_number, merge_commit_sha)` em `data/pr_list.json`. A lista
alimenta o `mine_pr()` (Dia 4) no caminho do mass mine #2 (Dia 12).

Estratégia de query (shard por (year, label) para escapar do teto de
1.000 resultados por search):

    is:pr is:merged language:python label:<label> merged:<year-01-01>..<year-12-31>

Labels alvos (configuráveis via CLI): refactoring, refactor, cleanup,
code-quality, tech-debt.

Auth: usa `gh api graphql` via subprocess — o `gh` CLI já está autenticado
no ambiente do sprint (token gho_... com scope `repo`). Sem variáveis de
ambiente; sem PAT custom.

Idempotência: rerun atualiza só PRs novos (merge por chave (repo, pr_number)).
"""
import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

# Labels de "refatoração-like" — uma query por label/ano (shard).
DEFAULT_LABELS = [
    "refactoring",
    "refactor",
    "cleanup",
    "code-quality",
    "tech-debt",
    "technical-debt",
]


_QUERY = """\
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        repository { nameWithOwner }
        number
        mergeCommit { oid }
        mergedAt
        title
      }
    }
  }
}
"""


def _gh_graphql(query: str, **vars) -> dict:
    """Invoca `gh api graphql` e retorna o JSON parsed."""
    cmd = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in vars.items():
        if v is None:
            continue
        cmd.extend(["-f", f"{k}={v}"])
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"gh api graphql falhou (exit {proc.returncode}):\n"
            f"  cmd: {' '.join(shlex.quote(c) for c in cmd[:5])} ...\n"
            f"  stderr: {proc.stderr.strip()[:500]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh retornou JSON inválido: {exc}\n{proc.stdout[:200]}")


def search_label_year(label: str, year: int, language: str = "python") -> list[dict]:
    """Coleta TODAS as páginas para um (label, year). Retorna lista de PRs:
    `[{repo, pr_number, merge_commit_sha, merged_at, title}, ...]`."""
    q = (f"is:pr is:merged language:{language} label:{label} "
         f"merged:{year}-01-01..{year}-12-31")
    cursor: str | None = None
    out: list[dict] = []
    page = 0
    while True:
        page += 1
        resp = _gh_graphql(_QUERY, q=q, cursor=cursor)
        if "errors" in resp:
            raise RuntimeError(f"GraphQL errors: {resp['errors']}")
        data = resp["data"]["search"]
        for node in data.get("nodes", []):
            # Filtragem por nó: PRs sem mergeCommit (cancelled?) não interessam.
            merge_commit = (node.get("mergeCommit") or {}).get("oid")
            if not merge_commit:
                continue
            out.append({
                "repo": node["repository"]["nameWithOwner"],
                "pr_number": node["number"],
                "merge_commit_sha": merge_commit,
                "merged_at": node.get("mergedAt"),
                "title": node.get("title"),
                "label": label,
                "year": year,
            })
        if not data["pageInfo"]["hasNextPage"]:
            break
        cursor = data["pageInfo"]["endCursor"]
    return out


def merge_cache(existing: list[dict], new: list[dict]) -> list[dict]:
    """Dedup por (repo, pr_number) — `new` tem precedência sobre `existing`."""
    by_key = {(p["repo"], p["pr_number"]): p for p in existing}
    for p in new:
        by_key[(p["repo"], p["pr_number"])] = p
    return sorted(by_key.values(),
                  key=lambda p: (p["repo"], p["pr_number"]))


def load_cache(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, prs: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prs, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", nargs="+", default=DEFAULT_LABELS,
                        help="labels a varrer (default: %(default)s)")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025],
                        help="anos a varrer (default: %(default)s)")
    parser.add_argument("--language", default="python")
    parser.add_argument("--output", type=Path,
                        default=Path("data/pr_list.json"),
                        help="arquivo de cache JSON (default: %(default)s)")
    parser.add_argument("--limit-shards", type=int, default=None,
                        help="processa apenas as primeiras N combinações (label, year) "
                        "— útil para smoke")
    args = parser.parse_args()

    existing = load_cache(args.output)
    print(f"Cache existente: {len(existing)} PRs em {args.output}")

    shards = [(L, Y) for L in args.labels for Y in args.years]
    if args.limit_shards is not None:
        shards = shards[: args.limit_shards]
        print(f"Limitado a {len(shards)} shards.")

    all_new: list[dict] = []
    for i, (label, year) in enumerate(shards, 1):
        print(f"[{i}/{len(shards)}] label={label!r} year={year} ...", flush=True)
        try:
            prs = search_label_year(label, year, language=args.language)
        except Exception as exc:
            print(f"  ERRO: {type(exc).__name__}: {exc}")
            continue
        print(f"  {len(prs)} PRs")
        all_new.extend(prs)

    merged = merge_cache(existing, all_new)
    save_cache(args.output, merged)
    print(f"\nCache atualizado: {len(merged)} PRs total "
          f"(+{len(merged) - len(existing)} novos vs existente).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
