"""Curador de pares minerados — estágio 4 (validação humana).

Serve uma UI web com os diffs dos pares; o revisor dá um veredito por par:

    clean    — refatoração limpa, entra no dataset como está
    noisy    — útil, mas o commit misturou mudanças não-relacionadas; o revisor
               recorta o par puro em before_clean/after_clean
    rejected — descartar

O veredito vai para um **sidecar** `data/reviews/<smell>.reviews.jsonl` (indexado
por `id`) — a saída da mineração (`data/raw/`) NUNCA é reescrita nem deletada.

Uso:
    python -m extracao.execucao.filtro_smells
    python -m extracao.execucao.filtro_smells --data data/raw --reviews data/reviews --port 5050
"""
import argparse
import difflib
import json
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, render_template_string, request

VALID_STATUS = {"clean", "noisy", "rejected"}

# ── HTML ─────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Curador</title>
<style>
  :root {
    --bg: #1e1e1e; --surface: #252526; --border: #3c3c3c;
    --add: #1e4620; --add-hl: #2ea043; --add-num: #163b18;
    --del: #4b1113; --del-hl: #f85149; --del-num: #3d0e10;
    --eq: #252526; --eq-num: #1e1e1e;
    --txt: #cccccc; --muted: #858585; --accent: #569cd6;
    --tag-bg: #0d2137; --tag-txt: #4fc1ff;
    --clean: #2ea043; --clean-bg: #16331c;
    --noisy: #d29922; --noisy-bg: #3a2d10;
    --reject: #f85149; --reject-bg: #3d0e10;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: var(--bg); color: var(--txt); font-size: 14px; }
  header { padding: 14px 28px; border-bottom: 1px solid var(--border);
           display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
           position: sticky; top: 0; background: var(--bg); z-index: 10; }
  header h1 { font-size: 1.05rem; font-weight: 600; color: var(--accent); }
  .stats { font-size: 0.82rem; color: var(--muted); }
  #counter { font-weight: 600; color: var(--txt); }
  .controls { margin-left: auto; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .controls label { font-size: 0.82rem; color: var(--muted); display: flex;
                    align-items: center; gap: 6px; cursor: pointer; }
  select { background: var(--surface); color: var(--txt); border: 1px solid var(--border);
           border-radius: 4px; padding: 5px 10px; font-size: 0.82rem; cursor: pointer; outline: none; }
  select:focus { border-color: var(--accent); }
  .pair { margin: 20px 28px; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
  .pair.st-clean   { border-left: 4px solid var(--clean); }
  .pair.st-noisy   { border-left: 4px solid var(--noisy); }
  .pair.st-rejected{ border-left: 4px solid var(--reject); opacity: 0.6; }
  .pair-header { background: var(--surface); padding: 10px 16px;
                 display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
                 border-bottom: 1px solid var(--border); }
  .pair-header .idx { color: var(--muted); font-size: 0.8rem; min-width: 32px; }
  .pair-header .fname { font-weight: 600; font-family: monospace; color: var(--accent); }
  .pair-header .repo { font-size: 0.78rem; color: var(--muted); }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 0.75rem;
         font-weight: 600; background: var(--tag-bg); color: var(--tag-txt); }
  .tag.verified { background: var(--clean-bg); color: var(--clean); }
  .tag.unverified { background: var(--reject-bg); color: var(--reject); }
  .diff-wrap { overflow-x: auto; }
  table.diff { width: 100%; border-collapse: collapse;
               font-family: "SF Mono", Menlo, Consolas, monospace;
               font-size: 0.82rem; line-height: 1.55; }
  table.diff td { padding: 1px 12px; white-space: pre; vertical-align: top; }
  td.num { width: 1%; min-width: 36px; text-align: right; padding: 1px 8px;
           user-select: none; color: var(--muted); border-right: 1px solid var(--border); }
  td.num.add { background: var(--add-num); color: var(--add-hl); }
  td.num.del { background: var(--del-num); color: var(--del-hl); }
  td.num.eq  { background: var(--eq-num); }
  td.code.add { background: var(--add); }
  td.code.del { background: var(--del); }
  td.code.eq  { background: var(--eq); }
  .sign { min-width: 14px; display: inline-block; }
  .hidden { display: none; }
  .empty { padding: 48px 28px; color: var(--muted); text-align: center; }
  .review-bar { padding: 10px 16px; display: flex; gap: 10px; align-items: center;
                flex-wrap: wrap; background: var(--surface); border-top: 1px solid var(--border); }
  .vbtn { border: 1px solid var(--border); border-radius: 4px; padding: 5px 14px;
          font-size: 0.82rem; font-weight: 600; cursor: pointer; background: var(--bg); color: var(--txt); }
  .vbtn.clean.on   { background: var(--clean-bg);  color: var(--clean);  border-color: var(--clean); }
  .vbtn.noisy.on   { background: var(--noisy-bg);  color: var(--noisy);  border-color: var(--noisy); }
  .vbtn.rejected.on{ background: var(--reject-bg); color: var(--reject); border-color: var(--reject); }
  .review-bar label { font-size: 0.8rem; color: var(--muted); display: flex; align-items: center; gap: 5px; }
  .review-bar input[type=text] { background: var(--bg); color: var(--txt);
       border: 1px solid var(--border); border-radius: 4px; padding: 4px 8px; font-size: 0.8rem; }
  .rstatus { margin-left: auto; font-size: 0.8rem; color: var(--muted); }
  .noisy-editor { padding: 12px 16px; display: none; gap: 12px; flex-direction: column;
                  background: var(--bg); border-top: 1px solid var(--border); }
  .noisy-editor.open { display: flex; }
  .noisy-editor textarea { width: 100%; min-height: 120px; background: var(--surface);
       color: var(--txt); border: 1px solid var(--border); border-radius: 4px; padding: 8px;
       font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.8rem; }
  .noisy-editor .lbl { font-size: 0.78rem; color: var(--muted); margin-bottom: 4px; }
  .toast { position: fixed; bottom: 24px; right: 28px; background: var(--clean-bg);
           color: var(--clean); padding: 10px 18px; border-radius: 6px; font-size: 0.88rem;
           opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 99; }
  .toast.show { opacity: 1; }
  .toast.error { background: var(--reject-bg); color: var(--reject); }
  .summary { padding: 20px 28px; color: var(--muted); font-size: 0.85rem;
             border-top: 1px solid var(--border); margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>Curador</h1>
  <span class="stats"><span id="counter">—</span></span>
  <div class="controls">
    <select id="smell-filter" onchange="loadPairs()">
      <option value="all">Todos os smells</option>
      {% for s in smells %}
      <option value="{{ s }}">{{ s }}</option>
      {% endfor %}
    </select>
    <select id="status-filter" onchange="loadPairs()">
      <option value="all">Todos os estados</option>
      <option value="pending">Só pendentes</option>
      <option value="reviewed">Só revisados</option>
    </select>
    <label><input type="checkbox" id="hide-eq" onchange="toggleEq(this)"> Ocultar linhas iguais</label>
  </div>
</header>

<div id="pairs-container"><div class="empty">Carregando...</div></div>

<div class="summary">Dados: <code>{{ data_dir }}</code> · vereditos em <code>{{ reviews_dir }}</code>
  (sidecar — a mineração nunca é alterada)</div>
<div class="toast" id="toast"></div>

<script>
  let hideEq = false;

  async function loadPairs() {
    const smell = document.getElementById('smell-filter').value;
    const status = document.getElementById('status-filter').value;
    const container = document.getElementById('pairs-container');
    container.innerHTML = '<div class="empty">Carregando...</div>';

    const res = await fetch('/pairs?smell=' + encodeURIComponent(smell)
                            + '&status=' + encodeURIComponent(status));
    const data = await res.json();
    document.getElementById('counter').textContent =
        data.pairs.length + ' exibidos · ' + data.reviewed + '/' + data.total + ' revisados';

    if (data.pairs.length === 0) {
      container.innerHTML = '<div class="empty">Nenhum par.</div>';
      return;
    }

    container.innerHTML = data.pairs.map((p, i) => {
      const rv = p._review || {};
      const st = rv.status || '';
      const bc = (rv.before_clean != null) ? rv.before_clean : p.before_code;
      const ac = (rv.after_clean  != null) ? rv.after_clean  : p.after_code;
      const vbadge = p.verified
        ? '<span class="tag verified">verificado</span>'
        : '<span class="tag unverified">nao-verificado</span>';
      return `
      <div class="pair ${st ? 'st-' + st : ''}" data-id="${esc(p.id)}" data-smell="${esc(p._smell_file)}">
        <div class="pair-header">
          <span class="idx">#${i + 1}</span>
          <span class="fname">${esc(p.function_name || '?')}</span>
          <span class="tag">${esc(p.smell_type || '?')}</span>
          ${vbadge}
          <span class="repo">${esc((p.repo||'').replace('https://github.com/',''))}
            · ${esc(p.file||'')} · <code>${esc((p.commit_hash||'').slice(0,7))}</code></span>
        </div>
        <div class="diff-wrap"><table class="diff">${p._diff}</table></div>
        <div class="review-bar">
          <button class="vbtn clean ${st==='clean'?'on':''}"       onclick="verdict(this,'clean')">Limpa</button>
          <button class="vbtn noisy ${st==='noisy'?'on':''}"       onclick="openNoisy(this)">Ruidosa</button>
          <button class="vbtn rejected ${st==='rejected'?'on':''}" onclick="verdict(this,'rejected')">Rejeitar</button>
          <label><input type="checkbox" class="oor" ${rv.out_of_rule?'checked':''}> fora da regra</label>
          <input type="text" class="notes" placeholder="notas" value="${esc(rv.notes||'')}">
          <span class="rstatus">${st ? 'veredito: ' + st : 'pendente'}</span>
        </div>
        <div class="noisy-editor ${st==='noisy'?'open':''}">
          <div><div class="lbl">before_clean (recorte o par puro)</div>
            <textarea class="bc">${esc(bc)}</textarea></div>
          <div><div class="lbl">after_clean</div>
            <textarea class="ac">${esc(ac)}</textarea></div>
          <button class="vbtn noisy" onclick="saveNoisy(this)">Salvar par recortado</button>
        </div>
      </div>`;
    }).join('');

    if (hideEq) toggleEq({ checked: true });
  }

  function _pairEl(node) { return node.closest('.pair'); }

  async function _send(pairEl, status, extra) {
    const body = Object.assign({
      smell: pairEl.dataset.smell,
      id: pairEl.dataset.id,
      status: status,
      out_of_rule: pairEl.querySelector('.oor').checked,
      notes: pairEl.querySelector('.notes').value,
    }, extra || {});
    const res = await fetch('/review', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) { showToast('Veredito salvo: ' + status); loadPairs(); }
    else { showToast('Erro: ' + data.error, true); }
  }

  function verdict(btn, status) { _send(_pairEl(btn), status); }

  function openNoisy(btn) {
    _pairEl(btn).querySelector('.noisy-editor').classList.toggle('open');
  }

  function saveNoisy(btn) {
    const pair = _pairEl(btn);
    _send(pair, 'noisy', {
      before_clean: pair.querySelector('.bc').value,
      after_clean: pair.querySelector('.ac').value,
    });
  }

  function toggleEq(cb) {
    hideEq = cb.checked;
    document.querySelectorAll('tr.eq-row').forEach(r => r.classList.toggle('hidden', hideEq));
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  let toastTimer;
  function showToast(msg, error=false) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show' + (error ? ' error' : '');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2500);
  }

  loadPairs();
</script>
</body></html>
"""

# ── Diff builder ─────────────────────────────────────────────────────────────

def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_diff_rows(before, after):
    bl, al = before.splitlines(), after.splitlines()
    matcher = difflib.SequenceMatcher(None, bl, al, autojunk=False)
    rows = []
    bn = an = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                bn += 1; an += 1
                ln = _esc(bl[i1 + k])
                rows.append(
                    f'<tr class="eq-row">'
                    f'<td class="num eq">{bn}</td><td class="code eq"><span class="sign"> </span>{ln}</td>'
                    f'<td class="num eq">{an}</td><td class="code eq"><span class="sign"> </span>{ln}</td>'
                    f'</tr>'
                )
        else:
            dl, il = bl[i1:i2], al[j1:j2]
            for k in range(max(len(dl), len(il))):
                dc = ic = dn = in_ = ""
                if k < len(dl):
                    bn += 1
                    dn = f'<td class="num del">{bn}</td>'
                    dc = f'<td class="code del"><span class="sign">−</span>{_esc(dl[k])}</td>'
                else:
                    dn = '<td class="num eq"></td>'; dc = '<td class="code eq"></td>'
                if k < len(il):
                    an += 1
                    in_ = f'<td class="num add">{an}</td>'
                    ic = f'<td class="code add"><span class="sign">+</span>{_esc(il[k])}</td>'
                else:
                    in_ = '<td class="num eq"></td>'; ic = '<td class="code eq"></td>'
                rows.append(f'<tr>{dn}{dc}{in_}{ic}</tr>')
    return "".join(rows)

# ── Sidecar de vereditos ─────────────────────────────────────────────────────

def load_reviews(reviews_dir: Path, smell: str) -> dict:
    """Vereditos do sidecar `<smell>.reviews.jsonl`, indexados por id."""
    path = reviews_dir / f"{smell}.reviews.jsonl"
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("id"):
                out[r["id"]] = r
    return out


def save_review(reviews_dir: Path, smell: str, review: dict) -> None:
    """Upsert de um veredito no sidecar (reescreve só o sidecar, nunca o raw)."""
    reviews_dir.mkdir(parents=True, exist_ok=True)
    reviews = load_reviews(reviews_dir, smell)
    reviews[review["id"]] = review
    path = reviews_dir / f"{smell}.reviews.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for r in reviews.values():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ── Carregamento de pares ────────────────────────────────────────────────────

def get_smells(data_dir: Path) -> list[str]:
    return sorted(p.stem for p in data_dir.glob("*.jsonl"))


def load_pairs(data_dir: Path, reviews_dir: Path, smell: str | None,
               status: str, limit: int) -> tuple[list[dict], int, int]:
    """Pares de `data/raw/`, com o veredito atual do sidecar anexado.

    Retorna (pares_exibidos, total, total_revisados)."""
    files = (
        [data_dir / f"{smell}.jsonl"] if smell and smell != "all"
        else sorted(data_dir.glob("*.jsonl"))
    )
    pairs, total, reviewed = [], 0, 0
    for f in files:
        if not f.exists():
            continue
        stem = f.stem
        reviews = load_reviews(reviews_dir, stem)
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            pid = p.get("id")
            review = reviews.get(pid) if pid else None
            if review:
                reviewed += 1
            if status == "pending" and review:
                continue
            if status == "reviewed" and not review:
                continue
            if len(pairs) >= limit:
                continue
            p["_diff"] = build_diff_rows(p.get("before_code", ""), p.get("after_code", ""))
            p["_smell_file"] = stem
            p["_review"] = review
            pairs.append(p)
    return pairs, total, reviewed

# ── Flask app ────────────────────────────────────────────────────────────────

def create_app(data_dir: Path, reviews_dir: Path, limit: int) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template_string(
            HTML, smells=get_smells(data_dir),
            data_dir=str(data_dir), reviews_dir=str(reviews_dir),
        )

    @app.route("/pairs")
    def pairs():
        smell = request.args.get("smell", "all")
        status = request.args.get("status", "all")
        loaded, total, reviewed = load_pairs(
            data_dir, reviews_dir, None if smell == "all" else smell, status, limit
        )
        return jsonify({"pairs": loaded, "total": total, "reviewed": reviewed})

    @app.route("/review", methods=["POST"])
    def review():
        body = request.get_json(silent=True) or {}
        smell = body.get("smell")
        pid = body.get("id")
        status = body.get("status")
        if not smell or not pid:
            return jsonify({"ok": False, "error": "smell e id obrigatorios"})
        if status not in VALID_STATUS:
            return jsonify({"ok": False, "error": f"status invalido: {status}"})
        record = {
            "id": pid,
            "status": status,
            "before_clean": body.get("before_clean"),
            "after_clean": body.get("after_clean"),
            "out_of_rule": bool(body.get("out_of_rule")),
            "reviewer": body.get("reviewer"),
            "notes": body.get("notes", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        save_review(reviews_dir, smell, record)
        return jsonify({"ok": True, "review": record})

    return app

# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw")
    ap.add_argument("--reviews", default="data/reviews")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--port", type=int, default=5050)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data)
    reviews_dir = Path(args.reviews)
    app = create_app(data_dir, reviews_dir, args.limit)

    if not args.no_open:
        Timer(1.0, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    print(f"Curador em → http://localhost:{args.port}")
    print(f"Dados:    {data_dir.resolve()}")
    print(f"Vereditos: {reviews_dir.resolve()}  (sidecar)")
    print("Ctrl+C para parar\n")
    app.run(port=args.port, debug=False)


if __name__ == "__main__":
    main()
