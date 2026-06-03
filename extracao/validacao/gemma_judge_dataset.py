"""
gemma_judge_dataset.py — Gemma 4 26B Q3 valida todos os pares minerados,
registrando veredito (real/aparente), confiança e justificativa.

Pula pares já avaliados (checkpoint incremental).
Salva em <dataset-dir>/anotacoes/anotacoes_gemma.json no mesmo formato
das anotações humanas.

Uso (a partir da raiz do repo de mineração, p.ex. smoke_c4/repo):
  python -m extracao.validacao.gemma_judge_dataset [--smells r1 r2 ...] [--dry-run]
  python -m extracao.validacao.gemma_judge_dataset --dataset-dir /caminho/para/tp-es2-dataset

Resolução do diretório do dataset (procura por <dir>/data/raw):
  1. argumento --dataset-dir
  2. variável de ambiente TP_DATASET_DIR
  3. repositório `tp-es2-dataset` irmão (subindo a árvore a partir deste arquivo)
  4. a raiz do próprio repo de mineração (onde `extracao.execucao.mineracao`
     escreve `data/raw/` quando rodado com CWD = raiz do repo)

IMPORTANTE (consistência): NÃO altere PROMPT, SMELL_CONTEXT nem os parâmetros
do modelo (MODEL/TEMPERATURE/NUM_PREDICT/NUM_CTX). Eles definem o critério de
validação e precisam ser idênticos entre todos os colaboradores.
"""
import argparse
import json
import os
import pathlib
import time
import datetime

import ollama

MODEL       = "batiai/gemma4-26b:q3"
NUM_PREDICT = 150
NUM_CTX     = 6144
TEMPERATURE = 0.1

# Preenchidos em main() após resolver o diretório do dataset.
DATASET_DIR: pathlib.Path | None = None
RAW_DIR:     pathlib.Path | None = None
ANNOT_PATH:  pathlib.Path | None = None

SMELL_MAP = {
    "r1": ("long_method",    "R1"),
    "r2": ("long_param_list","R2"),
    "r3": ("magic_numbers",  "R3"),
    "r4": ("deep_nesting",   "R4"),
    "r5": ("dead_code",      "R5"),
}

SMELL_CONTEXT = {
    "R1": (
        "Extract Method (Long Method)",
        "BEFORE must be a long, complex function with multiple responsibilities. "
        "AFTER must have the main function clearly shorter, delegating work to one or more extracted helper functions. "
        "A valid refactoring preserves all original logic without introducing new behavior."
    ),
    "R2": (
        "Introduce Parameter Object (Long Parameter List)",
        "BEFORE must have a function with too many parameters (typically 4+). "
        "AFTER must group related parameters into a single object, dataclass, or named tuple, "
        "reducing the parameter count of the main function. Logic must be preserved."
    ),
    "R3": (
        "Replace Magic Number/String with Named Constant",
        "BEFORE must contain literal values (numbers or strings) that encode domain knowledge "
        "without a descriptive name. AFTER must replace them with module-level named constants "
        "(e.g. ALL_CAPS names). The constants must be meaningful, not just aliases."
    ),
    "R4": (
        "Replace Nested Conditionals with Guard Clauses (Deep Nesting)",
        "BEFORE must have deeply nested conditionals (if inside if inside if, typically 3+ levels). "
        "AFTER must reduce nesting by using early returns or guard clauses, making the happy path "
        "linear and obvious. Logic must be preserved exactly."
    ),
    "R5": (
        "Remove Dead Code",
        "BEFORE must contain unreachable code, unused variables, or logically impossible branches. "
        "AFTER must remove only the dead code, keeping all reachable behavior intact. "
        "The removal must be clean — no stubs or comments left behind."
    ),
}

PROMPT = """You are an expert software engineer evaluating refactoring quality.

Smell being checked: {smell_name}
Rule: {smell_rule}

BEFORE:
```python
{before_code}
```

AFTER:
```python
{after_code}
```

Is this a REAL, correct refactoring of the {smell_name} smell?
Answer on the FIRST LINE with exactly one word: REAL or APARENTE (if it is a false positive, wrong refactoring, or introduces logic changes).
Answer on the SECOND LINE with confidence: alta, media, or baixa.
Answer on the THIRD LINE with a one-sentence justification in Portuguese.

Answer:"""


def resolve_dataset_dir(cli_value: str | None) -> pathlib.Path:
    """Acha o diretório que contém `data/raw/` (ver docstring do módulo)."""
    candidatos: list[pathlib.Path] = []
    if cli_value:
        candidatos.append(pathlib.Path(cli_value).expanduser())
    env = os.environ.get("TP_DATASET_DIR")
    if env:
        candidatos.append(pathlib.Path(env).expanduser())
    # repo `tp-es2-dataset` irmão, subindo a árvore a partir deste arquivo
    aqui = pathlib.Path(__file__).resolve()
    for parent in aqui.parents:
        candidatos.append(parent / "tp-es2-dataset")
    # raiz do próprio repo de mineração (extracao/validacao/.. -> repo/)
    candidatos.append(aqui.parents[2])

    for c in candidatos:
        if (c / "data" / "raw").is_dir():
            return c.resolve()

    raise SystemExit(
        "Não encontrei o diretório do dataset (esperado <dir>/data/raw).\n"
        "Use --dataset-dir /caminho/para/tp-es2-dataset ou defina TP_DATASET_DIR."
    )


def load_checkpoint() -> dict:
    if ANNOT_PATH.exists():
        return json.loads(ANNOT_PATH.read_text(encoding="utf-8"))
    return {
        "pesquisador": "Gemma 4 26B Q3 (batiai/gemma4-26b:q3)",
        "versao": "v1",
        "atualizadoEm": datetime.datetime.now().isoformat(),
        "totalExemplos": 0,
        "completos": 0,
        "anotacoes": {},
    }


def save_checkpoint(state: dict):
    state["atualizadoEm"] = datetime.datetime.now().isoformat()
    ANNOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ANNOT_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def call_gemma(smell_type: str, before_code: str, after_code: str) -> tuple[str, str, str]:
    """Retorna (veredito, confianca, justificativa)."""
    smell_name, smell_rule = SMELL_CONTEXT[smell_type]
    prompt = (PROMPT
              .replace("{smell_name}", smell_name)
              .replace("{smell_rule}", smell_rule)
              .replace("{before_code}", before_code)
              .replace("{after_code}", after_code))

    resp = ollama.generate(
        model=MODEL,
        prompt=prompt,
        think=False,
        options={"temperature": TEMPERATURE, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
    )
    text = (resp.response or "").strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    veredito    = "aparente"
    confianca   = "media"
    justificativa = text

    if lines:
        first = lines[0].upper()
        if "REAL" in first and "APARENTE" not in first:
            veredito = "real"
        elif "APARENTE" in first:
            veredito = "aparente"

    if len(lines) >= 2:
        sec = lines[1].lower()
        if "alta" in sec:
            confianca = "alta"
        elif "baixa" in sec:
            confianca = "baixa"
        else:
            confianca = "media"

    if len(lines) >= 3:
        justificativa = " ".join(lines[2:])

    return veredito, confianca, justificativa


def load_pairs(smell_file: str) -> list[dict]:
    path = RAW_DIR / smell_file
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smells", nargs="+", default=["r1","r2","r3","r4","r5"],
                        choices=list(SMELL_MAP.keys()),
                        help="Smells a processar (default: todos)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Apenas lista os pares sem chamar o modelo")
    parser.add_argument("--pilot", type=int, default=0,
                        help="Modo pilot: avalia apenas N pares por smell (0 = sem limite)")
    parser.add_argument("--dataset-dir", default=None,
                        help="Diretório que contém data/raw/ (default: TP_DATASET_DIR ou autodetecção)")
    args = parser.parse_args()

    global DATASET_DIR, RAW_DIR, ANNOT_PATH
    DATASET_DIR = resolve_dataset_dir(args.dataset_dir)
    RAW_DIR     = DATASET_DIR / "data" / "raw"
    ANNOT_PATH  = DATASET_DIR / "anotacoes" / "anotacoes_gemma.json"
    print(f"Dataset: {DATASET_DIR}")
    print(f"  pares: {RAW_DIR}")
    print(f"  anotações: {ANNOT_PATH}")

    state = load_checkpoint()
    done_ids: set = set(state["anotacoes"].keys())
    print(f"Checkpoint: {len(done_ids)} pares já avaliados")

    total_new = 0
    total_real = 0
    total_aparente = 0
    session_start = time.perf_counter()

    for smell_key in args.smells:
        smell_file, smell_type = SMELL_MAP[smell_key]
        pairs = load_pairs(f"{smell_file}.jsonl")
        pending = [p for p in pairs if p.get("id") and p["id"] not in done_ids]

        real_in_smell = sum(1 for pid, a in state["anotacoes"].items()
                            if a.get("smell") == smell_type and a.get("veredito") == "real")

        print(f"\n{'='*60}")
        print(f"{smell_type} ({smell_file}): {len(pairs)} total | {len(pending)} pendentes | {real_in_smell} já aprovados")
        print(f"{'='*60}")

        if args.dry_run:
            for p in pending[:5]:
                print(f"  id={p['id']} repo={p.get('repo','?')} func={p.get('function_name','?')}")
            if len(pending) > 5:
                print(f"  ... +{len(pending)-5} mais")
            continue

        if args.pilot > 0:
            pending = pending[:args.pilot]
            print(f"  [PILOT] limitado a {args.pilot} pares")

        for rank, pair in enumerate(pending, 1):
            pid    = pair["id"]
            before = pair.get("before_code", "")
            after  = pair.get("after_code",  "")
            func   = pair.get("function_name", "?")
            repo   = pair.get("repo", "?")

            print(f"  [{rank}/{len(pending)}] {repo} · {func}", end=" | ", flush=True)

            try:
                t0 = time.perf_counter()
                veredito, confianca, justificativa = call_gemma(smell_type, before, after)
                elapsed = time.perf_counter() - t0

                mark = "✓ REAL" if veredito == "real" else "✗ APARENTE"
                print(f"{mark} ({confianca}, {elapsed:.0f}s)")

                state["anotacoes"][pid] = {
                    "veredito":      veredito,
                    "confianca":     confianca,
                    "justificativa": justificativa,
                    "smell":         smell_type,
                    "ts":            datetime.datetime.now().isoformat(),
                }
                state["completos"] = len(state["anotacoes"])

                if veredito == "real":
                    total_real += 1
                else:
                    total_aparente += 1
                total_new += 1

                save_checkpoint(state)

            except Exception as e:
                print(f"ERRO: {e}")

            # ETA a cada 20 pares
            if rank % 20 == 0:
                elapsed_total = time.perf_counter() - session_start
                n_done_session = total_new
                if n_done_session > 0:
                    avg = elapsed_total / n_done_session
                    remaining_in_smell = len(pending) - rank
                    print(f"    ETA {smell_type}: {remaining_in_smell * avg / 60:.0f} min restantes")

    # Relatório final
    total_annotated = len(state["anotacoes"])
    print(f"\n{'='*60}")
    print(f"SESSÃO CONCLUÍDA")
    print(f"  Novos avaliados:  {total_new}")
    print(f"    ✓ REAL:         {total_real}")
    print(f"    ✗ APARENTE:     {total_aparente}")
    print(f"  Total acumulado:  {total_annotated}")
    print(f"  Salvo em:         {ANNOT_PATH}")
    print(f"{'='*60}")

    # Sumário por smell
    print("\nResumo por smell:")
    for sk, (sf, st) in SMELL_MAP.items():
        pairs = load_pairs(f"{sf}.jsonl")
        annotated = [a for pid, a in state["anotacoes"].items() if a.get("smell") == st]
        real = sum(1 for a in annotated if a["veredito"] == "real")
        print(f"  {st}: {len(annotated)}/{len(pairs)} avaliados | {real} REAL ({real*100//len(annotated) if annotated else 0}%)")


if __name__ == "__main__":
    main()
