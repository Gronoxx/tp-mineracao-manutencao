"""Fase D — Mineração dos primeiros anos de cada repo.

Premissa: refatoração é mais comum nos primeiros anos de um projeto
(crescimento rápido, refator de métodos longos especialmente). Esta fase
minera os primeiros 7 anos de cada repo NÃO cobertos por mass mines
anteriores.

Regra:
- Se `created_at >= 2015`: skip (primeiros 7 anos cobertos por Fase A+B).
- Caso contrário: minerar `[created_at, min(created_at+7y, 2014-12-31)]`.

Input: arquivo JSON com lista de objetos `{repo, since, to, months}`.
Por padrão usa `/tmp/c5_first_years_config.json` gerado por separate one-liner.

Uso:
    python3 scripts/c5_first_years_mine.py
    python3 scripts/c5_first_years_mine.py --config /tmp/c5_first_years_config.json
    python3 scripts/c5_first_years_mine.py --no-require-keyword  # default kw=False já
"""
import argparse
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extracao.execucao.mineracao import CAP_POR_SMELL, SMELLS, _orcamento_repo  # noqa: E402
from extracao.mineracao.minerador import mine  # noqa: E402


def run(config: list[dict], output: Path,
        require_keyword: bool = False,
        partial_threshold: float = 0.1) -> dict[str, int]:
    print(f"=== Fase D — First-7-years mine — {len(config)} repos ===")
    print(f"  require_keyword={require_keyword}, "
          f"partial_threshold={partial_threshold}")
    print(f"  Caps por smell: {CAP_POR_SMELL}\n", flush=True)

    total: dict[str, int] = {s: 0 for s in SMELLS}
    falhas: list[tuple[str, str]] = []
    t_inicio = time.time()

    for i, entry in enumerate(config):
        if all(total[s] >= CAP_POR_SMELL[s] for s in SMELLS):
            print(f"\nTodos os smells atingiram o cap — encerrando.")
            break

        repo = entry["repo"]
        since = datetime.strptime(entry["since"], "%Y-%m-%d")
        to = datetime.strptime(entry["to"], "%Y-%m-%d")
        nome = repo.rsplit("/", 1)[-1]
        caps = _orcamento_repo(total, repos_restantes=len(config) - i)
        ti = time.time()
        print(f"[{time.strftime('%H:%M:%S')}] [{i+1}/{len(config)}] {nome} "
              f"({since.date()}–{to.date()}, orçamento {caps}) ...",
              flush=True)

        try:
            counts = mine(repo_url=repo, output_path=output,
                          since=since, to=to, caps=caps,
                          partial_threshold=partial_threshold,
                          require_keyword=require_keyword)
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
    if falhas:
        print(f"\n{len(falhas)} repos falharam:")
        for nome, msg in falhas:
            print(f"  - {nome}: {msg}")
    print(f"\nPares escritos em {output}/")
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path,
                        default=Path("/tmp/c5_first_years_config.json"),
                        help="JSON com lista de {repo, since, to}")
    parser.add_argument("--out", type=Path, default=Path("data/raw"),
                        help="diretório de saída (default data/raw)")
    parser.add_argument("--require-keyword", action="store_true",
                        help="liga filtro de keyword (default DESLIGADO para max yield)")
    parser.add_argument("--partial-threshold", type=float, default=0.1)
    args = parser.parse_args()

    if not args.config.exists():
        print(f"ERRO: config {args.config} não existe", file=sys.stderr)
        return 1

    with args.config.open() as f:
        config = json.load(f)

    run(config, output=args.out,
        require_keyword=args.require_keyword,
        partial_threshold=args.partial_threshold)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
