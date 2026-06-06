#!/usr/bin/env python3
"""Piloto — PR mining do label `code-quality` do home-assistant/core.

Cadeia (mesmo pipeline da produção, para o yield ser comparável):
  1. fetch: PRs merged com label code-quality (GitHub REST API) -> merge_commit_shas
  2. mine:  mine_pr() sobre os merge commits (usa clone LOCAL pré-feito) -> pares por smell
  3. judge: Gemma julga cada par (REAL/APARENTE), com orçamento de tempo
  4. report: yield por smell

Não toca em data/raw canônico — escreve em --out separado e num arquivo de
anotações próprio. Checkpoint por par (sobrevive a interrupção).

Uso:
  # smoke (mede tempo de clone/mine/judge):
  python3 pilot_ha_codequality.py --max-prs 5 --clone-path ../../.pilot_clones/ha-core
  # piloto ~2h:
  python3 pilot_ha_codequality.py --max-prs 400 --clone-path ../../.pilot_clones/ha-core --judge-budget-min 80
  # só buscar SHAs (sem minerar):
  python3 pilot_ha_codequality.py --fetch-only --max-prs 400 --clone-path x
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent          # raiz do repo (contem extracao/)
PROJECT_ROOT = REPO_DIR                              # raiz do projeto (gemma_judge_dataset.py mora aqui)
sys.path.insert(0, str(REPO_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from extracao.mineracao.minerador import mine_pr     # noqa: E402
import gemma_judge_dataset as judge                  # noqa: E402  (reusa call_gemma/SMELL_MAP)

TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = "home-assistant/core"
LABEL = "code-quality"
PILOT_DIR = REPO_DIR / "pilot_out"
SHAS_PATH = PILOT_DIR / "ha_codequality_shas.json"
ANNOT_PATH = PILOT_DIR / "pilot_annotations.json"
RAW_OUT = PILOT_DIR / "raw"

# nome do arquivo jsonl (detector) -> código do smell para o juiz
FILE_TO_RCODE = {sf: rc for (sf, rc) in judge.SMELL_MAP.values()}


def _api(path: str):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Authorization": f"Bearer {TOKEN}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "refac-pilot"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_pr_shas(max_prs: int, max_files: int = 3, scan_cap: int = 0) -> list[str]:
    """Coleta merge SHAs de PRs code-quality ATÔMICOS (changed_files <= max_files).
    PRs grandes são lentos de minerar e raramente são refatoração de um único
    smell — filtrá-los acelera e melhora a precisão (filtro diff-atomic).
    Varre até `scan_cap` PRs (0 = ilimitado até achar max_prs atômicos)."""
    q = urllib.parse.quote(f'repo:{REPO} is:pr is:merged label:"{LABEL}"')
    nums: list[int] = []
    page = 1
    cap = scan_cap or (max_prs * 6)   # heurística: varre ~6x para achar atômicos
    while len(nums) < cap and page <= 10:
        data = _api(f"/search/issues?per_page=100&page={page}&sort=created&order=desc&q={q}")
        items = data.get("items", [])
        if not items:
            break
        nums += [it["number"] for it in items]
        if len(items) < 100:
            break
        page += 1
        time.sleep(2)
    nums = nums[:cap]
    print(f"  varrendo {len(nums)} PRs (filtro: changed_files<= {max_files})...", flush=True)
    shas: list[str] = []
    scanned = 0
    for n in nums:
        try:
            pr = _api(f"/repos/{REPO}/pulls/{n}")
            scanned += 1
            cf = pr.get("changed_files", 9999)
            sha = pr.get("merge_commit_sha")
            if sha and cf <= max_files:
                shas.append(sha)
        except Exception as e:
            print(f"    PR #{n}: {type(e).__name__}", flush=True)
        if scanned % 50 == 0:
            print(f"    ...varridos {scanned}, atômicos {len(shas)}", flush=True)
            time.sleep(1)
        if len(shas) >= max_prs:
            break
    print(f"  {len(shas)} PRs atômicos de {scanned} varridos "
          f"({100*len(shas)/max(scanned,1):.0f}% atômicos)", flush=True)
    return shas


def load_annot() -> dict:
    if ANNOT_PATH.exists():
        return json.loads(ANNOT_PATH.read_text(encoding="utf-8"))
    return {"repo": REPO, "label": LABEL, "anotacoes": {}}


def save_annot(state: dict):
    state["atualizadoEm"] = datetime.datetime.now().isoformat()
    ANNOT_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def judge_pairs(budget_min: float):
    state = load_annot()
    done = set(state["anotacoes"].keys())
    deadline = time.perf_counter() + budget_min * 60
    counts = Counter()      # smell -> total julgado
    reals = Counter()       # smell -> REAL
    for f in sorted(RAW_OUT.glob("*.jsonl")):
        rcode = FILE_TO_RCODE.get(f.stem)
        if rcode is None:
            continue
        pairs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        for p in pairs:
            pid = p.get("id")
            if not pid or pid in done:
                if pid in done:
                    a = state["anotacoes"][pid]
                    counts[rcode] += 1
                    reals[rcode] += (a["veredito"] == "real")
                continue
            if time.perf_counter() > deadline:
                print("  [orçamento de julgamento esgotado]", flush=True)
                save_annot(state)
                return counts, reals, True
            before = p.get("before_code", "")
            after = p.get("after_code", "")
            try:
                t0 = time.perf_counter()
                ver, conf, just = judge.call_gemma(rcode, before, after)
                dt = time.perf_counter() - t0
            except Exception as e:
                print(f"    judge ERRO {pid[:8]}: {e}", flush=True)
                continue
            state["anotacoes"][pid] = {"veredito": ver, "confianca": conf,
                                       "justificativa": just, "smell": rcode,
                                       "repo": p.get("repo"), "source": p.get("source")}
            save_annot(state)
            counts[rcode] += 1
            reals[rcode] += (ver == "real")
            mark = "REAL" if ver == "real" else "apar"
            print(f"    {rcode} {pid[:8]} {mark} ({dt:.0f}s)", flush=True)
    return counts, reals, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-prs", type=int, default=300)
    ap.add_argument("--max-files", type=int, default=3,
                    help="filtro diff-atomic: só PRs com changed_files <= isto")
    ap.add_argument("--clone-path", required=True,
                    help="caminho do clone LOCAL do home-assistant (passado ao mine_pr)")
    ap.add_argument("--judge-budget-min", type=float, default=80.0)
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--skip-fetch", action="store_true",
                    help="reusa SHAs já salvos em ha_codequality_shas.json")
    args = ap.parse_args()

    PILOT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_OUT.mkdir(parents=True, exist_ok=True)
    if not TOKEN:
        print("ERRO: GITHUB_TOKEN ausente"); return 1

    # 1. FETCH
    if args.skip_fetch and SHAS_PATH.exists():
        shas = json.loads(SHAS_PATH.read_text())
        print(f"[fetch] reusando {len(shas)} SHAs de {SHAS_PATH}")
    else:
        print(f"[fetch] {REPO} label={LABEL} max={args.max_prs}")
        t = time.perf_counter()
        shas = fetch_pr_shas(args.max_prs, max_files=args.max_files)
        SHAS_PATH.write_text(json.dumps(shas, indent=2))
        print(f"[fetch] {len(shas)} merge SHAs em {time.perf_counter()-t:.0f}s -> {SHAS_PATH}")
    if args.fetch_only:
        return 0

    # 2. MINE
    clone_path = args.clone_path
    if not Path(clone_path).exists():
        print(f"ERRO: clone local {clone_path} não existe — clone primeiro"); return 1
    print(f"[mine] mine_pr sobre {len(shas)} merge commits (clone local: {clone_path})")
    t = time.perf_counter()
    counts = mine_pr(repo_url=clone_path, output_path=RAW_OUT,
                     merge_commit_shas=shas, partial_threshold=0.1)
    mine_t = time.perf_counter() - t
    total_cands = sum(counts.values())
    print(f"[mine] {total_cands} candidatos em {mine_t:.0f}s ({mine_t/max(len(shas),1):.1f}s/PR)")
    print(f"[mine] por smell: {dict(counts)}")

    # 3. JUDGE
    print(f"[judge] orçamento {args.judge_budget_min} min")
    t = time.perf_counter()
    cj, rj, hit_budget = judge_pairs(args.judge_budget_min)
    print(f"[judge] {time.perf_counter()-t:.0f}s (orçamento atingido: {hit_budget})")

    # 4. REPORT
    print("\n" + "=" * 56)
    print(f"PILOTO home-assistant/code-quality — {len(shas)} PRs")
    print(f"  candidatos minerados: {total_cands} ({dict(counts)})")
    print("  yield (julgados):")
    for rc in ["R1", "R2", "R3", "R4", "R5"]:
        j = cj.get(rc, 0); r = rj.get(rc, 0)
        if j:
            print(f"    {rc}: {r}/{j} REAL ({100*r/j:.0f}%)")
    tj = sum(cj.values()); tr = sum(rj.values())
    print(f"  TOTAL: {tr}/{tj} REAL" + (f" ({100*tr/tj:.0f}%)" if tj else ""))
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
