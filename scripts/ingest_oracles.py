"""Ingestão de catálogos de oracles externos para `data/test/`.

Dia 2 do sprint (C3). Lê PyRef CSV + arquivos do Sourcery examples,
mapeia para `OracleEntry` e grava jsonl em `data/test/`. Não extrai
código — isso é responsabilidade do Dia 3 (adjacent mining) que roda
nosso pipeline nos `commit_hash` do catálogo.

Uso:
    python3 scripts/ingest_oracles.py --pyref-csv path/to/dataset.csv

Fontes:
    PyRef:    https://raw.githubusercontent.com/PyRef/PyRef/main/data/dataset.csv
    Sourcery: https://github.com/sourcery-ai/examples (refactorings/)
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional

# Permite rodar `python3 scripts/ingest_oracles.py` da raiz do repo sem
# precisar de `python3 -m`. (Mesmo padrão das fixtures do pytest via conftest.)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.oracle import OracleEntry  # noqa: E402


# Mapeamento PyRef refactoring type -> nosso código R1..R5.
# Só "Extract Method" tem correspondente direto (R1). Os demais ficam None
# (catálogo bibliográfico apenas).
PYREF_TO_SMELL = {
    "Extract Method": "R1",
    "Inline Method": "R1",      # inverso de Extract — ainda informativo para R1
    # Os tipos abaixo NÃO mapeiam para os 5 smells do TP:
    "Rename Method": None,
    "Move Method": None,
    "Pull Up Method": None,
    "Push Down Method": None,
    "Add Parameter": None,
    "Remove Parameter": None,
    "Change/Rename Parameter": None,
}


def parse_pyref_commit_url(url: str) -> tuple[Optional[str], Optional[str]]:
    """Extrai (repo_url, commit_hash) de uma URL no formato
    https://github.com/<owner>/<name>/commit/<hash>."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/commit/([0-9a-f]+)", url.strip())
    if not m:
        return None, None
    owner, name, sha = m.group(1), m.group(2), m.group(3)
    return f"https://github.com/{owner}/{name}", sha


def parse_pyref_description(desc: str) -> tuple[Optional[str], Optional[str]]:
    """Extrai (file, function_name) do campo `description` quando possível.

    Formato observado: "Location: dit/algorithms/jsd.py\nThe method "JSD" is renamed to ..."
    """
    file_match = re.search(r"Location:\s*([^\s\n]+)", desc or "")
    file = file_match.group(1) if file_match else None
    # method name entre aspas — pega a primeira ocorrência
    method_match = re.search(r'"([A-Za-z_][A-Za-z0-9_]*)"', desc or "")
    func = method_match.group(1) if method_match else None
    return file, func


def ingest_pyref(csv_path: Path, output_path: Path) -> int:
    """Lê PyRef CSV e escreve `data/test/oracle_pyref_test.jsonl`.

    Retorna o número de entradas escritas.
    """
    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    entries: list[OracleEntry] = []
    for row in rows:
        url = row.get("commit", "").strip()
        if not url:
            continue
        repo, commit_hash = parse_pyref_commit_url(url)
        if repo is None:
            continue
        ext_type = (row.get("refactoring type") or "").strip()
        smell = PYREF_TO_SMELL.get(ext_type)
        validation_raw = (row.get("validation") or "unknown").strip()
        validation = validation_raw if validation_raw in {"TP", "FP", "CTP"} else "unknown"
        desc = (row.get("description") or "").strip() or None
        file, func = parse_pyref_description(desc or "")
        entries.append(OracleEntry(
            source_dataset="pyref",
            external_refactoring_type=ext_type,
            validation=validation,
            repo=repo,
            commit_hash=commit_hash,
            file=file,
            function_name=func,
            smell_type=smell,
            description=desc,
            tool=(row.get("tool") or "").strip() or None,
            notes=(row.get("note") or "").strip() or None,
        ))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(e.model_dump_json(exclude_none=False) + "\n")
    return len(entries)


def ingest_sourcery(examples_dir: Path, output_path: Path) -> int:
    """Lê arquivos *.py do Sourcery examples e gera entradas-pointer.

    Os arquivos contêm apenas o código "before" (input para a ferramenta
    Sourcery). Cada `def`/`class` vira uma `OracleEntry` referenciando o
    arquivo e a função, com `smell_type=None` (Sourcery cobre vários smells
    sem mapeamento 1-1 com o TP) — é catálogo bibliográfico.
    """
    import ast as _ast
    entries: list[OracleEntry] = []
    for py_file in sorted(examples_dir.glob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = _ast.parse(source)
        except SyntaxError:
            continue
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                entries.append(OracleEntry(
                    source_dataset="sourcery",
                    external_refactoring_type=f"sourcery_example:{py_file.stem}",
                    validation="unknown",
                    repo="https://github.com/sourcery-ai/examples",
                    file=str(py_file.name),
                    function_name=node.name,
                    smell_type=None,
                    description=f"Sourcery refactoring demo file ({py_file.name}); função `{node.name}` é input ilustrativo.",
                    tool="sourcery",
                ))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(e.model_dump_json(exclude_none=False) + "\n")
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyref-csv", type=Path,
                        help="caminho local do PyRef dataset.csv (já baixado)")
    parser.add_argument("--sourcery-dir", type=Path,
                        help="diretório local com os arquivos do sourcery-ai/examples/refactorings")
    parser.add_argument("--out-dir", type=Path, default=Path("data/test"),
                        help="diretório de saída (default: data/test)")
    args = parser.parse_args()

    if not args.pyref_csv and not args.sourcery_dir:
        print("ERRO: pelo menos uma fonte (--pyref-csv ou --sourcery-dir) é obrigatória",
              file=sys.stderr)
        return 1

    total = 0
    if args.pyref_csv:
        if not args.pyref_csv.exists():
            print(f"ERRO: {args.pyref_csv} não existe", file=sys.stderr)
            return 1
        n = ingest_pyref(args.pyref_csv, args.out_dir / "oracle_pyref_test.jsonl")
        print(f"PyRef: {n} entradas em {args.out_dir/'oracle_pyref_test.jsonl'}")
        total += n
    if args.sourcery_dir:
        if not args.sourcery_dir.is_dir():
            print(f"ERRO: {args.sourcery_dir} não é diretório", file=sys.stderr)
            return 1
        n = ingest_sourcery(args.sourcery_dir, args.out_dir / "oracle_sourcery_test.jsonl")
        print(f"Sourcery: {n} entradas em {args.out_dir/'oracle_sourcery_test.jsonl'}")
        total += n
    print(f"\nTotal: {total} entradas de oracle catalogadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
