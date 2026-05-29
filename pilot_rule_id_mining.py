#!/usr/bin/env python3
"""Mineração ancorada em rule-ID de linter (R2/R3/R4) — nativo, via API, sem clonar.

Para cada smell, busca commits que mencionam o rule-ID do linter (ruff/pylint),
baixa o diff dos .py via API (conteúdo before@parent / after@sha), roda os
detectores do projeto (extract_candidates + verify_pair) e julga com o Gemma.

Não clona repos (escala para muitos repos, 1-poucos commits cada). Saída isolada
em rule_mining_out/. Checkpoint por par no fetch/mine e no judge.

Uso:
  python3 pilot_rule_id_mining.py --smells R2 --max-commits 8 --judge-budget-min 3   # smoke
  python3 pilot_rule_id_mining.py --smells R2 R3 R4 --max-commits 600                 # batch (judge ilimitado)
"""
import argparse, base64, datetime, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REPO_DIR.parent.parent
sys.path.insert(0, str(REPO_DIR)); sys.path.insert(0, str(PROJECT_ROOT))
from extracao.mineracao.minerador import extract_candidates, verify_pair  # noqa: E402
import gemma_judge_dataset as judge  # noqa: E402

TOKEN = os.environ.get("GITHUB_TOKEN")
OUT = REPO_DIR / "rule_mining_out"
RAW = OUT / "raw"
SHAS = OUT / "commits_seen.json"
ANNOT = OUT / "annotations.json"
FILE_TO_RCODE = {sf: rc for (sf, rc) in judge.SMELL_MAP.values()}

# rule-ID + token estrutural por smell (commit search no message)
RULES = {
    "R2": ['PLR0913 dataclass', 'PLR0913 extract', 'R0913 dataclass', 'PLR0913 parameter'],
    "R3": ['PLR2004 constant', 'PLR2004 extract', 'R2004 constant', 'PLR2004 magic'],
    "R4": ['PLR1702 guard', 'PLR1702 early return', 'R1702 nested', 'PLR1702 refactor'],
}


def api(path: str, retries: int = 5):
    for attempt in range(retries):
        req = urllib.request.Request(
            "https://api.github.com" + path,
            headers={"Authorization": f"Bearer {TOKEN}",
                     "Accept": "application/vnd.github+json", "User-Agent": "rule-miner"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):  # rate limit
                reset = e.headers.get("X-RateLimit-Reset")
                wait = max(5, int(reset) - int(time.time())) if reset else 30
                wait = min(wait, 120)
                print(f"    [rate-limit {e.code}] dormindo {wait}s", flush=True)
                time.sleep(wait + 1)
                continue
            if e.code == 404:
                return None
            raise
    return None


def search_commits(query: str, max_results: int) -> list[tuple]:
    out, page = [], 1
    while len(out) < max_results and page <= 10:
        d = api(f"/search/commits?per_page=100&page={page}&q={urllib.parse.quote(query)}")
        if not d:
            break
        items = d.get("items", [])
        for it in items:
            out.append((it["repository"]["full_name"], it["sha"]))
        if len(items) < 100:
            break
        page += 1
        time.sleep(3)  # commit search ~30/min
    return out


def get_file(repo: str, path: str, ref: str):
    d = api(f"/repos/{repo}/contents/{urllib.parse.quote(path)}?ref={ref}")
    if d and d.get("encoding") == "base64":
        try:
            return base64.b64decode(d["content"]).decode("utf-8", "replace")
        except Exception:
            return None
    return None


def mine_commit(repo: str, sha: str) -> list:
    c = api(f"/repos/{repo}/commits/{sha}")
    if not c or not c.get("parents"):
        return []
    parent = c["parents"][0]["sha"]
    msg = c.get("commit", {}).get("message", "")
    # ignora commits de bot
    author = (c.get("author") or {}).get("login", "") or ""
    if author.endswith("[bot]") or "bot" == author.lower():
        return []
    recs = []
    for f in c.get("files", []):
        path = f.get("filename", "")
        if not path.endswith(".py") or "test" in path.lower():
            continue
        if f.get("status") != "modified":
            continue
        before = get_file(repo, path, parent)
        after = get_file(repo, path, sha)
        if not before or not after:
            continue
        try:
            for cand in extract_candidates(before, after, path):
                for rec in verify_pair(cand, repo=f"https://github.com/{repo}", commit_hash=sha,
                                       parent_commit=parent, commit_msg=msg, msg_keywords=[],
                                       filename=path, partial_threshold=0.1, source="rule_id_mined"):
                    recs.append(rec)
        except Exception:
            continue
    return recs


def load_json(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def fetch_and_mine(smells, max_commits):
    RAW.mkdir(parents=True, exist_ok=True)
    seen = set(load_json(SHAS, []))
    written = Counter()
    for smell in smells:
        commits = []
        for q in RULES[smell]:
            commits += search_commits(q, max_commits)
        # dedupe por (repo,sha), tira já vistos
        uniq = []
        for repo, sha in commits:
            key = f"{repo}@{sha}"
            if key in seen:
                continue
            seen.add(key); uniq.append((repo, sha))
        uniq = uniq[:max_commits]
        print(f"[{smell}] {len(uniq)} commits novos para minerar", flush=True)
        for i, (repo, sha) in enumerate(uniq, 1):
            recs = mine_commit(repo, sha)
            for rec in recs:
                d = rec.model_dump()
                with open(RAW / f"{rec.smell_type}.jsonl", "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(d, ensure_ascii=False) + "\n")
                written[rec.smell_type] += 1
            if i % 25 == 0:
                print(f"  [{smell}] {i}/{len(uniq)} commits | candidatos até agora: {dict(written)}", flush=True)
                SHAS.write_text(json.dumps(sorted(seen)))
    SHAS.write_text(json.dumps(sorted(seen)))
    print(f"[mine] candidatos escritos por smell: {dict(written)}", flush=True)
    return written


def judge_all(budget_min: float):
    state = load_json(ANNOT, {"anotacoes": {}})
    done = set(state["anotacoes"].keys())
    deadline = (time.perf_counter() + budget_min * 60) if budget_min > 0 else None
    counts, reals = Counter(), Counter()
    for f in sorted(RAW.glob("*.jsonl")):
        pairs = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        # dedupe por id dentro do arquivo
        byid = {p["id"]: p for p in pairs if p.get("id")}
        for pid, p in byid.items():
            rc = p.get("smell_type")
            if rc not in ("R1", "R2", "R3", "R4", "R5"):
                continue
            if pid in done:
                a = state["anotacoes"][pid]; counts[rc] += 1; reals[rc] += (a["veredito"] == "real"); continue
            if deadline and time.perf_counter() > deadline:
                print("  [orçamento de judge esgotado]", flush=True)
                ANNOT.write_text(json.dumps(state, ensure_ascii=False, indent=2));
                return counts, reals
            try:
                ver, conf, just = judge.call_gemma(rc, p.get("before_code", ""), p.get("after_code", ""))
            except Exception as e:
                print(f"    judge ERRO {pid[:8]}: {e}", flush=True); continue
            state["anotacoes"][pid] = {"veredito": ver, "confianca": conf, "justificativa": just,
                                       "smell": rc, "repo": p.get("repo"), "source": p.get("source")}
            ANNOT.write_text(json.dumps(state, ensure_ascii=False, indent=2))
            counts[rc] += 1; reals[rc] += (ver == "real")
            print(f"    {rc} {pid[:8]} {'REAL' if ver=='real' else 'apar'}", flush=True)
    return counts, reals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--smells", nargs="+", default=["R2", "R3", "R4"], choices=["R2", "R3", "R4"])
    ap.add_argument("--max-commits", type=int, default=600, help="máx. commits por smell")
    ap.add_argument("--judge-budget-min", type=float, default=0.0, help="0 = ilimitado")
    ap.add_argument("--mine-only", action="store_true")
    args = ap.parse_args()
    if not TOKEN:
        print("ERRO: GITHUB_TOKEN ausente"); return 1
    OUT.mkdir(parents=True, exist_ok=True)

    print(f"=== FETCH+MINE smells={args.smells} max_commits={args.max_commits} ===", flush=True)
    written = fetch_and_mine(args.smells, args.max_commits)
    if args.mine_only:
        return 0

    print(f"=== JUDGE (budget {args.judge_budget_min or 'ilimitado'} min) ===", flush=True)
    counts, reals = judge_all(args.judge_budget_min)

    print("\n" + "=" * 56)
    print("RULE-ID MINING — resultado")
    for rc in ["R2", "R3", "R4"]:
        j = counts.get(rc, 0); r = reals.get(rc, 0)
        if j:
            print(f"  {rc}: {r}/{j} REAL ({100*r/j:.0f}%)")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
