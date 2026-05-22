"""Parametrized mass mine runner para esgotamento dos 36 repos curados.

Usa a mesma lista REPOS de `extracao/execucao/mineracao.py` mas permite
configurar `since`/`to`/`require_keyword`/`cross_file_threshold` via CLI.
Útil para rodar fases distintas do esgotamento (Fase A: janela temporal
ampliada; Fase B: kw=False; Fase C: cross-file ativado).

Uso:
    # Fase A — expansão temporal (delta 2015-2019 vs 2020-2024 já feito)
    python3 scripts/exhaust_curated_mine.py \\
        --since 2015-01-01 --to 2019-12-31

    # Fase B — kw=False janela 2020-2024
    python3 scripts/exhaust_curated_mine.py \\
        --since 2020-01-01 --to 2024-12-31 \\
        --no-require-keyword

    # Fase C-2 — cross-file ativado janela 2020-2024
    python3 scripts/exhaust_curated_mine.py \\
        --since 2020-01-01 --to 2024-12-31 \\
        --cross-file-threshold 0.7

Idempotente: o merge por `id` dentro de `mine()` evita duplicados quando
re-rodado.
"""
import argparse
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# Permite rodar `python3 scripts/exhaust_curated_mine.py` da raiz do repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extracao.execucao.mineracao import REPOS, CAP_POR_SMELL, SMELLS, _orcamento_repo  # noqa: E402
from extracao.mineracao.minerador import mine  # noqa: E402


def run(since: datetime, to: datetime, output: Path,
        require_keyword: bool = True,
        cross_file_threshold: float | None = None,
        identifier_overlap_threshold: float = 0.0,
        partial_threshold: float = 0.1) -> dict[str, int]:
    print(f"=== Exhaust curated — {len(REPOS)} repos, "
          f"janela {since.date()}–{to.date()} ===")
    print(f"  require_keyword={require_keyword}, "
          f"cross_file_threshold={cross_file_threshold}, "
          f"identifier_overlap_threshold={identifier_overlap_threshold}, "
          f"partial_threshold={partial_threshold}")
    print(f"  Caps: {CAP_POR_SMELL}\n", flush=True)

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

        kwargs = dict(
            repo_url=repo,
            output_path=output,
            since=since,
            to=to,
            caps=caps,
            partial_threshold=partial_threshold,
            require_keyword=require_keyword,
            identifier_overlap_threshold=identifier_overlap_threshold,
        )
        if cross_file_threshold is not None:
            kwargs["cross_file_threshold"] = cross_file_threshold

        try:
            counts = mine(**kwargs)
        except Exception as exc:
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
    print(f"\nPares escritos em {output}/")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--since", required=True,
                        help="YYYY-MM-DD início da janela de commits")
    parser.add_argument("--to", required=True,
                        help="YYYY-MM-DD fim da janela de commits")
    parser.add_argument("--out", type=Path, default=Path("data/raw"),
                        help="diretório de saída (default data/raw)")
    parser.add_argument("--no-require-keyword", action="store_true",
                        help="desliga filtro de keyword na mensagem do commit (G3)")
    parser.add_argument("--cross-file-threshold", type=float, default=None,
                        help="threshold AST similarity para cross-file (default None)")
    parser.add_argument("--identifier-overlap-threshold", type=float, default=0.0,
                        help="threshold Jaccard identifier overlap (default 0.0)")
    parser.add_argument("--partial-threshold", type=float, default=0.1,
                        help="threshold E1 (default 0.1)")
    args = parser.parse_args()

    since = datetime.strptime(args.since, "%Y-%m-%d")
    to = datetime.strptime(args.to, "%Y-%m-%d")
    run(since=since, to=to, output=args.out,
        require_keyword=not args.no_require_keyword,
        cross_file_threshold=args.cross_file_threshold,
        identifier_overlap_threshold=args.identifier_overlap_threshold,
        partial_threshold=args.partial_threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
