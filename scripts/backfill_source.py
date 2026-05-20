"""Backfill do campo `source` em pares minerados antes do sprint.

D5 do sprint de mineração — todos os pares já em `data/raw/*.jsonl` foram
produzidos pelo pipeline em commit-mode, portanto recebem `source="mined_commit"`.

Idempotente: registros que já têm `source` são preservados (não sobrescritos),
permitindo re-execução sem efeito colateral. Reportagem por arquivo deixa
claro quantos foram atualizados vs. quantos já estavam taggeados.
"""
import argparse
import json
import sys
from pathlib import Path


DEFAULT_SOURCE = "mined_commit"


def backfill_file(path: Path, source: str = DEFAULT_SOURCE) -> tuple[int, int, int]:
    """Lê o jsonl, adiciona `source` onde faltar, regrava no lugar.

    Retorna (total_linhas, ja_taggeados, atualizados).
    """
    lines_in = path.read_text(encoding="utf-8").splitlines()
    total = 0
    already = 0
    updated = 0
    lines_out: list[str] = []
    for raw in lines_in:
        stripped = raw.strip()
        if not stripped:
            lines_out.append(raw)
            continue
        total += 1
        record = json.loads(stripped)
        if "source" in record and record["source"] is not None:
            already += 1
        else:
            record["source"] = source
            updated += 1
        # `ensure_ascii=False` preserva acentos/caracteres unicode dos
        # snippets de código; `separators` mantém formato compacto jsonl.
        lines_out.append(json.dumps(record, ensure_ascii=False))
    # Reescreve só se houver mudança (evita touch desnecessário do mtime).
    if updated > 0:
        path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    return total, already, updated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default="data/raw",
        help="diretório com os arquivos *.jsonl a serem backfilled (default: data/raw)",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"valor a atribuir ao campo source (default: {DEFAULT_SOURCE})",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"ERRO: {data_dir} não é diretório", file=sys.stderr)
        return 1

    files = sorted(data_dir.glob("*.jsonl"))
    if not files:
        print(f"ERRO: nenhum *.jsonl em {data_dir}", file=sys.stderr)
        return 1

    print(f"Backfilling source={args.source!r} em {len(files)} arquivo(s):")
    grand_total = grand_already = grand_updated = 0
    for f in files:
        total, already, updated = backfill_file(f, source=args.source)
        grand_total += total
        grand_already += already
        grand_updated += updated
        print(
            f"  {f.name}: {total} registros, "
            f"{already} já taggeados, {updated} atualizados"
        )
    print(
        f"\nTotal: {grand_total} registros · "
        f"{grand_already} já taggeados · {grand_updated} atualizados"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
