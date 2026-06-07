#!/usr/bin/env python3
"""Qualidade da classe positiva (REAL) + gerador da amostra de anotação.

(1) Para cada par REAL (Gemma=REAL) atribui EVIDÊNCIA DE PADRÃO-AST do refactoring
    esperado por smell — o proxy `ast_pattern_match`. Checa o MECANISMO (não só o
    delta de métrica — distingue refatoração genuína de "métrica caiu por deleção").
(2) Exporta a amostra de anotação `positive_quality_sample.json` (10 por smell, com
    mistura true/false para calibrar o proxy) no schema do anotador
    (ver tp-es2-anotador/QUALIDADE.md) e `positive_quality_sample.meta.json` com as
    TAXAS-BASE por smell (real / flag_true / flag_false). A amostra balanceada é
    enviesada por construção; as taxas-base permitem ao scorer reponderar os estratos
    e reportar a precisão populacional P(genuína | Gemma=REAL) além de
    P(gen|flag=true) / P(gen|flag=false).

Portável: caminho do dataset via --dataset-dir / env TP_DATASET_DIR / autodetecção.
Sem caminhos absolutos e sem segredos.

Uso:
    python estimate_positive_quality.py --dataset-dir /caminho/para/tp-es2-dataset
"""
import argparse
import ast
import glob
import json
import os
import pathlib
import random
import re
from collections import defaultdict

NEST = (ast.If, ast.For, ast.While, ast.With, ast.Try, ast.AsyncFor, ast.AsyncWith)
TRIVIAL = {0, 1, 2, -1, "", " ", "\n"}
R_ORDER = ["R1", "R2", "R3", "R4", "R5"]


def resolve_dataset_dir(cli):
    """Acha o diretório do dataset (precisa de data/raw + anotacoes_gemma.json)."""
    cands = []
    if cli:
        cands.append(pathlib.Path(cli).expanduser())
    env = os.environ.get("TP_DATASET_DIR")
    if env:
        cands.append(pathlib.Path(env).expanduser())
    here = pathlib.Path(__file__).resolve()
    for p in here.parents:
        cands.append(p / "tp-es2-dataset")
    for c in cands:
        if (c / "data" / "raw").is_dir() and (c / "anotacoes" / "anotacoes_gemma.json").exists():
            return c.resolve()
    raise SystemExit(
        "Dataset não encontrado (esperado <dir>/data/raw e "
        "<dir>/anotacoes/anotacoes_gemma.json). Use --dataset-dir ou TP_DATASET_DIR."
    )


def load_reals(ds):
    """Os pares REAL = join de data/raw com os veredictos 'real' do Gemma."""
    raw = {}
    for f in glob.glob(str(ds / "data" / "raw" / "*.jsonl")):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                raw[r["id"]] = r
    ann = json.load(open(ds / "anotacoes" / "anotacoes_gemma.json", encoding="utf-8"))["anotacoes"]
    return [raw[p] for p, a in ann.items() if a["veredito"] == "real" and p in raw]


def funcs(code):
    try:
        tree = ast.parse(code)
    except Exception:
        return None
    return {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def n_params(fn):
    a = fn.args
    return len(a.posonlyargs) + len(a.args) + len(a.kwonlyargs) + bool(a.vararg) + bool(a.kwarg)


def calls(fn):
    out = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                out.add(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                out.add(n.func.attr)
    return out


def attrs(fn):
    return {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}


def names(fn):
    return {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}


def literals(node):
    return [n.value for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float, str))]


def depth(node, cur=0):
    d = cur + (1 if isinstance(node, NEST) else 0)
    best = d
    for c in ast.iter_child_nodes(node):
        best = max(best, depth(c, d))
    return best


def guards(fn):
    return sum(1 for n in ast.walk(fn)
               if isinstance(n, ast.If) and n.body
               and isinstance(n.body[-1], (ast.Return, ast.Raise, ast.Continue, ast.Break)))


def main_fn(d, name):
    if not d:
        return None
    if name and name in d:
        return d[name]
    if name and name.split(".")[-1] in d:
        return d[name.split(".")[-1]]
    return next(iter(d.values()), None)


def pattern_match(r):
    """Retorna (nome_do_padrao, casou_bool) — o proxy ast_pattern_match."""
    s = r["smell_type"]
    bc = r["before_code"]
    ac = r["after_code"]
    bf, af = funcs(bc), funcs(ac)
    if bf is None or af is None:
        return ("parse_fail", False)
    nm = r.get("function_name")
    mb, ma = r.get("metrics_before") or {}, r.get("metrics_after") or {}

    if s == "R1":  # Extract Method: surge helper QUE A MAIN CHAMA + main encurta
        new = set(af) - set(bf)
        m = main_fn(af, nm)
        shrank = mb.get("lines_of_code", 0) > ma.get("lines_of_code", 10 ** 9) if "lines_of_code" in mb else True
        return ("extract_method", bool(new) and bool(m and (calls(m) & new)) and shrank)

    if s == "R2":  # Parameter Object: cai >=2 params E os removidos viram obj.attr
        best = False
        for name in set(bf) & set(af):
            drop = n_params(bf[name]) - n_params(af[name])
            if drop >= 2:
                removed = (
                    {a.arg for a in (bf[name].args.posonlyargs + bf[name].args.args + bf[name].args.kwonlyargs)}
                    - {a.arg for a in (af[name].args.posonlyargs + af[name].args.args + af[name].args.kwonlyargs)}
                )
                if removed & attrs(af[name]):
                    best = True
        return ("parameter_object", best)

    if s == "R3":  # Named Constant: literal some E surge nome ALL_CAPS na função
        m_b, m_a = main_fn(bf, nm), main_fn(af, nm)
        if not (m_b and m_a):
            return ("named_constant", False)
        lb = {x for x in literals(m_b) if x not in TRIVIAL}
        la = set(literals(m_a))
        removed = lb - la
        new_const = {n for n in names(m_a) if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", n)} - names(m_b)
        return ("named_constant", bool(removed) and bool(new_const))

    if s == "R4":  # Guard Clauses: cai aninhamento E aumentam early-returns
        m_b, m_a = main_fn(bf, nm), main_fn(af, nm)
        if not (m_b and m_a):
            return ("guard_clauses", False)
        depth_drop = depth(m_b) > depth(m_a)
        more_guards = guards(m_a) > guards(m_b)
        return ("guard_clauses", depth_drop and more_guards)

    if s == "R5":  # Dead Code: encurta E nada novo (deleção pura)
        new = set(af) - set(bf)
        shrank = len(ac.splitlines()) < len(bc.splitlines())
        return ("dead_code_removal", shrank and not new)

    return ("?", False)


def build_sample(reals, res):
    """10 por smell, ~5 true + 5 false (backfill se um estrato faltar). seed=42."""
    by = defaultdict(list)
    for r in reals:
        by[r["smell_type"]].append(r)
    random.seed(42)
    sample = []
    for s in R_ORDER:
        pool = by[s]
        trues = [r for r in pool if res[r["id"]]]
        falses = [r for r in pool if not res[r["id"]]]
        random.shuffle(trues)
        random.shuffle(falses)
        pick = trues[:5] + falses[:5]
        if len(pick) < 10:  # estrato fino (ex.: R1 só tem 1 false) -> completa com o outro
            rest = [r for r in (trues + falses) if r not in pick]
            pick += rest[:10 - len(pick)]
        for i, r in enumerate(pick, 1):
            sample.append((s, i, r))
    return sample


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-dir", default=None,
                    help="diretório do tp-es2-dataset (default: TP_DATASET_DIR ou autodetecção)")
    ap.add_argument("--out", default=None, help="saída da amostra (default: <dataset>/positive_quality_sample.json)")
    ap.add_argument("--meta", default=None, help="saída das taxas-base (default: <dataset>/positive_quality_sample.meta.json)")
    args = ap.parse_args()

    ds = resolve_dataset_dir(args.dataset_dir)
    out = pathlib.Path(args.out) if args.out else ds / "positive_quality_sample.json"
    meta_out = pathlib.Path(args.meta) if args.meta else ds / "positive_quality_sample.meta.json"

    reals = load_reals(ds)
    res = {r["id"]: pattern_match(r)[1] for r in reals}

    # (b) taxas-base por smell sobre TODOS os REAL (para o scorer reponderar)
    base = defaultdict(lambda: [0, 0])  # smell -> [flag_true, flag_false]
    for r in reals:
        base[r["smell_type"]][0 if res[r["id"]] else 1] += 1
    tt = sum(v[0] for v in base.values())
    tf = sum(v[1] for v in base.values())
    print(f"=== {len(reals)} REAL — proxy ast_pattern_match (taxa-base) ===")
    print(f"{'smell':6}{'REAL':>6}{'flag_true':>11}{'flag_false':>12}")
    for s in R_ORDER:
        t, f = base[s]
        print(f"{s:6}{t + f:>6}{t:>11}{f:>12}")
    print(f"{'TOTAL':6}{tt + tf:>6}{tt:>11}{tf:>12}  ({100 * tt // (tt + tf)}% true)")

    # (a) amostra de anotação no schema do contrato
    sample = build_sample(reals, res)
    items = []
    comp = defaultdict(lambda: [0, 0])
    for s, i, r in sample:
        m = bool(res[r["id"]])
        comp[s][0 if m else 1] += 1
        items.append({
            "id": f"{s.lower()}_{i:06d}",
            "smell": r["smell_type"],
            "before": r["before_code"],
            "after": r["after_code"],
            "ast_pattern_match": m,
            "repo": r.get("repo"),
            "file": r.get("file"),
            "function_name": r.get("function_name"),
            "commit_hash": r.get("commit_hash"),
            "source": r.get("source"),
        })

    meta = {
        "populacao": f"{len(reals)} REAL (Gemma=real)",
        "seed": 42,
        "taxa_base_por_smell": {s: {"real": base[s][0] + base[s][1],
                                    "flag_true": base[s][0],
                                    "flag_false": base[s][1]} for s in R_ORDER},
        "amostra_por_smell": {s: {"true": comp[s][0], "false": comp[s][1],
                                  "n": comp[s][0] + comp[s][1]} for s in R_ORDER},
        "nota": ("Amostra ~5 true/5 false por smell para CALIBRAR o proxy; é enviesada por "
                 "construção. Use taxa_base_por_smell para reponderar os estratos e obter a "
                 "precisão populacional P(genuína|REAL), além de P(gen|true)/P(gen|false). "
                 "R1 tem apenas 1 par flag_false em toda a população -> o estrato false de R1 "
                 "não é calibrável (déficit conhecido)."),
    }

    out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_out.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nAmostra: {len(items)} pares (10/smell) -> {out}")
    print(f"  composição por smell:", {s: tuple(comp[s]) for s in R_ORDER}, "(true,false)")
    print(f"Taxas-base -> {meta_out}")


if __name__ == "__main__":
    main()
