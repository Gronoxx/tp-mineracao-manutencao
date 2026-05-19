"""Atribuição de pares minerados para revisão dupla — apoio à curadoria.

Lê os `<smell>.jsonl` de `data/raw/`, distribui os pares em 3 blocos
estratificados por smell e atribui cada bloco a um par de revisores, com um
terceiro como adjudicador (D1). Grava `data/reviews/assignment.json`.

D2 — `data/raw/` permanece imutável: a atribuição vive num arquivo separado.

Uso:
    python -m extracao.execucao.gerar_blocos
    python -m extracao.execucao.gerar_blocos --revisores ana bruno caio --seed 7
"""
import argparse
import json
import random
from pathlib import Path

N_BLOCOS = 3


def _coletar_pares(raw_dir: Path) -> list[dict]:
    """Pares de todos os `<smell>.jsonl` de `raw_dir` — `id` + `smell` (o stem
    do arquivo, p.ex. `long_method`), para o curador/curate saberem o sidecar."""
    pares: list[dict] = []
    for jf in sorted(raw_dir.glob("*.jsonl")):
        smell = jf.stem
        for line in jf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("id"):
                pares.append({"id": rec["id"], "smell": smell})
    return pares


def assign_blocks(pares: list[dict], revisores: list[str], seed: int = 42) -> dict:
    """Distribui `pares` em 3 blocos estratificados por smell.

    Cada smell é embaralhado (com `seed`) e distribuído round-robin entre os 3
    blocos — cada bloco fica com ~1/3 de cada smell. Os blocos recebem pares de
    revisores em rodízio: B1={r0,r1} adj r2; B2={r1,r2} adj r0; B3={r2,r0} adj r1
    — cada revisor é primário em 2 blocos e adjudicador em 1.
    """
    if len(revisores) != 3:
        raise ValueError(
            f"a revisao dupla precisa de exatamente 3 revisores; recebi {revisores}"
        )
    if len(set(revisores)) != 3:
        raise ValueError(f"os 3 revisores devem ser distintos; recebi {revisores}")

    rng = random.Random(seed)
    baldes: list[list[dict]] = [[] for _ in range(N_BLOCOS)]
    por_smell: dict[str, list[dict]] = {}
    for p in pares:
        por_smell.setdefault(p["smell"], []).append(p)
    for smell in sorted(por_smell):
        grupo = list(por_smell[smell])
        rng.shuffle(grupo)
        for i, par in enumerate(grupo):
            baldes[i % N_BLOCOS].append(par)

    blocos = []
    for b in range(N_BLOCOS):
        r0, r1, r2 = (revisores[b % 3], revisores[(b + 1) % 3], revisores[(b + 2) % 3])
        blocos.append({
            "id": f"B{b + 1}",
            "revisores": [r0, r1],
            "adjudicator": r2,
            "pares": baldes[b],
        })
    return {"seed": seed, "revisores": list(revisores), "blocos": blocos}


def write_assignment(path: str | Path, assignment: dict, force: bool = False) -> None:
    """Grava `assignment.json`. Recusa sobrescrever sem `force` — realocar
    blocos invalidaria os vereditos `(id, revisor)` já coletados."""
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(
            f"{path} ja existe — use --force para sobrescrever (atencao: "
            f"realocar blocos invalida vereditos ja coletados)."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(assignment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Gera a atribuicao de blocos para revisao dupla (assignment.json)."
    )
    ap.add_argument("--raw-dir", default="data/raw",
                    help="Diretorio com os <smell>.jsonl do minerador")
    ap.add_argument("--out", default="data/reviews/assignment.json",
                    help="Destino do assignment.json")
    ap.add_argument("--revisores", nargs=3, default=["A", "B", "C"],
                    metavar=("REV1", "REV2", "REV3"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--force", action="store_true",
                    help="Sobrescreve um assignment.json existente")
    args = ap.parse_args(argv)

    pares = _coletar_pares(Path(args.raw_dir))
    if not pares:
        raise SystemExit(f"Nenhum par em {args.raw_dir} — rode o minerador primeiro.")
    assignment = assign_blocks(pares, args.revisores, seed=args.seed)
    write_assignment(args.out, assignment, force=args.force)

    print(f"{len(pares)} pares -> {N_BLOCOS} blocos em {args.out}")
    for b in assignment["blocos"]:
        print(f"  {b['id']}: {len(b['pares'])} pares · "
              f"revisores {b['revisores']} · adjudicador {b['adjudicator']}")


if __name__ == "__main__":
    main()
