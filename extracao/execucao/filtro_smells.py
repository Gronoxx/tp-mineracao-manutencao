"""
Servidor de curadoria de pares minerados.
Serve o HTML com diffs e permite deletar pares diretamente pelo browser.

Uso:
    python -m extracao.execucao.filtro_smells
    python -m extracao.execucao.filtro_smells --data data/raw --port 5050 --smell long_method --limit 100
                                                (local dados)   (porta)      (filtrar smells)   (quantidade limite de smells)
"""

import argparse
import difflib
import json
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, render_template_string, request

# ── HTML ─────────────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Curator</title>
<style>
  :root {
    --bg: #1e1e1e; --surface: #252526; --border: #3c3c3c;
    --add: #1e4620; --add-hl: #2ea043; --add-num: #163b18;
    --del: #4b1113; --del-hl: #f85149; --del-num: #3d0e10;
    --eq: #252526; --eq-num: #1e1e1e;
    --txt: #cccccc; --muted: #858585; --accent: #569cd6;
    --tag-bg: #0d2137; --tag-txt: #4fc1ff;
    --danger: #f85149; --danger-bg: #3d0e10;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: var(--bg); color: var(--txt); font-size: 14px; }
  header { padding: 14px 28px; border-bottom: 1px solid var(--border);
           display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
           position: sticky; top: 0; background: var(--bg); z-index: 10; }
  header h1 { font-size: 1.05rem; font-weight: 600; color: var(--accent); }
  .stats { font-size: 0.82rem; color: var(--muted); }
  #remaining { font-weight: 600; color: var(--txt); }
  .controls { margin-left: auto; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  .controls label { font-size: 0.82rem; color: var(--muted); display: flex;
                    align-items: center; gap: 6px; cursor: pointer; }
  select {
    background: var(--surface); color: var(--txt); border: 1px solid var(--border);
    border-radius: 4px; padding: 5px 10px; font-size: 0.82rem; cursor: pointer;
    outline: none;
  }
  select:focus { border-color: var(--accent); }

  #pairs-container { min-height: 200px; }
  .pair { margin: 20px 28px; border: 1px solid var(--border); border-radius: 6px;
          overflow: hidden; }
  .pair-header { background: var(--surface); padding: 10px 16px;
                 display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
                 border-bottom: 1px solid var(--border); }
  .pair-header .idx { color: var(--muted); font-size: 0.8rem; min-width: 32px; }
  .pair-header .fname { font-weight: 600; font-family: monospace; color: var(--accent); }
  .pair-header .repo { font-size: 0.78rem; color: var(--muted); }
  .pair-header .actions { margin-left: auto; }
  .tag { display: inline-block; padding: 1px 8px; border-radius: 3px; font-size: 0.75rem;
         font-weight: 600; background: var(--tag-bg); color: var(--tag-txt); }
  .btn-delete { background: var(--danger-bg); color: var(--danger);
                border: 1px solid var(--danger); border-radius: 4px; padding: 4px 12px;
                font-size: 0.8rem; cursor: pointer; font-weight: 600; }
  .btn-delete:hover { background: #5a1010; }
  .btn-delete:disabled { opacity: 0.4; cursor: default; }
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
  .empty { padding: 48px 28px; color: var(--muted); font-size: 0.95rem; text-align: center; }
  .toast { position: fixed; bottom: 24px; right: 28px; background: #2d6a4f;
           color: #d5ead9; padding: 10px 18px; border-radius: 6px; font-size: 0.88rem;
           opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 99; }
  .toast.show { opacity: 1; }
  .toast.error { background: var(--danger-bg); color: var(--danger); }
  .summary { padding: 20px 28px; color: var(--muted); font-size: 0.85rem;
             border-top: 1px solid var(--border); margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>Curator</h1>
  <span class="stats"><span id="remaining">—</span> pairs</span>
  <div class="controls">
    <select id="smell-filter" onchange="loadPairs()">
      <option value="all">All smells</option>
      {% for s in smells %}
      <option value="{{ s }}">{{ s }}</option>
      {% endfor %}
    </select>
    <label><input type="checkbox" id="hide-eq" onchange="toggleEq(this)"> Hide unchanged</label>
  </div>
</header>

<div id="pairs-container"><div class="empty">Loading...</div></div>

<div class="summary">Serving <code>{{ data_dir }}</code> · changes written to disk immediately</div>
<div class="toast" id="toast"></div>

<script>
  let hideEq = false;

  async function loadPairs() {
    const smell = document.getElementById('smell-filter').value;
    const container = document.getElementById('pairs-container');
    container.innerHTML = '<div class="empty">Loading...</div>';

    const res  = await fetch('/pairs?smell=' + encodeURIComponent(smell));
    const data = await res.json();

    document.getElementById('remaining').textContent = data.length + ' / ' + data.total;

    if (data.pairs.length === 0) {
      container.innerHTML = '<div class="empty">No pairs found.</div>';
      return;
    }

    container.innerHTML = data.pairs.map((p, i) => `
      <div class="pair" id="pair-${i}">
        <div class="pair-header">
          <span class="idx">#${i + 1}</span>
          <span class="fname">${esc(p.name)}</span>
          <span class="tag">${esc(p.smell)}</span>
          <span class="repo">${esc(p.repo.replace('https://github.com/', ''))} · ${esc(p.file)} · <code>${p.commit.slice(0,7)}</code></span>
          <div class="actions">
            <button class="btn-delete"
              onclick="deletePair(this, ${i}, '${p.smell}', '${p.commit}', ${p._line})">
              Delete
            </button>
          </div>
        </div>
        <div class="diff-wrap">
          <table class="diff">${p._diff}</table>
        </div>
      </div>
    `).join('');

    if (hideEq) toggleEq({ checked: true });
  }

  async function deletePair(btn, idx, smell, commit, line) {
    btn.disabled = true;
    const res  = await fetch('/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ smell, commit, line })
    });
    const data = await res.json();
    if (data.ok) {
      showToast('Deleted — ' + data.removed + ' line(s) removed from ' + smell + '.jsonl');
      await loadPairs();   // recarrega a lista atualizada
    } else {
      showToast('Error: ' + data.error, true);
      btn.disabled = false;
    }
  }

  function toggleEq(cb) {
    hideEq = cb.checked;
    document.querySelectorAll('tr.eq-row').forEach(r => {
      r.classList.toggle('hidden', hideEq);
    });
  }

  function esc(s) {
    return String(s)
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

  // carrega ao iniciar
  loadPairs();
</script>
</body></html>
"""

# ── Diff builder ──────────────────────────────────────────────────────────────

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
                    ic  = f'<td class="code add"><span class="sign">+</span>{_esc(il[k])}</td>'
                else:
                    in_ = '<td class="num eq"></td>'; ic = '<td class="code eq"></td>'
                rows.append(f'<tr>{dn}{dc}{in_}{ic}</tr>')
    return "".join(rows)

# ── Data loading ──────────────────────────────────────────────────────────────

def load_pairs(data_dir: Path, smell: str | None, limit: int) -> list[dict]:
    files = (
        [data_dir / f"{smell}.jsonl"] if smell and smell != "all"
        else sorted(data_dir.glob("*.jsonl"))
    )
    pairs = []
    for f in files:
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh):
                line = line.strip()
                if not line:
                    continue
                try:
                    p = json.loads(line)
                except json.JSONDecodeError:
                    continue
                p["_diff"] = build_diff_rows(p["before"], p["after"])
                p["_line"] = lineno
                pairs.append(p)
                if len(pairs) >= limit:
                    break
    return pairs

def get_smells(data_dir: Path) -> list[str]:
    return sorted(p.stem for p in data_dir.glob("*.jsonl"))

# ── Flask app ─────────────────────────────────────────────────────────────────

def create_app(data_dir: Path, limit: int) -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        smells = get_smells(data_dir)
        return render_template_string(HTML, smells=smells, data_dir=str(data_dir))

    @app.route("/pairs")
    def pairs():
        smell = request.args.get("smell", "all")
        loaded = load_pairs(data_dir, smell if smell != "all" else None, limit)
        # total sem limit (para o contador)
        total = sum(
            sum(1 for ln in open(f, encoding="utf-8") if ln.strip())
            for f in (
                [data_dir / f"{smell}.jsonl"] if smell != "all"
                else data_dir.glob("*.jsonl")
            )
            if Path(f).exists()
        )
        return jsonify({"pairs": loaded, "length": len(loaded), "total": total})

    @app.route("/delete", methods=["POST"])
    def delete():
        body          = request.get_json()
        target_smell  = body["smell"]
        target_commit = body["commit"]
        target_line   = body["line"]

        jsonl_path = data_dir / f"{target_smell}.jsonl"
        if not jsonl_path.exists():
            return jsonify({"ok": False, "error": "file not found"})

        lines = jsonl_path.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines = []
        removed = 0
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if not stripped:
                new_lines.append(ln)
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                new_lines.append(ln)
                continue
            if rec.get("commit") == target_commit and i == target_line:
                removed += 1
            else:
                new_lines.append(ln)

        jsonl_path.write_text("".join(new_lines), encoding="utf-8")
        return jsonify({"ok": True, "removed": removed})

    return app

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data",    default="data/raw")
    ap.add_argument("--limit",   type=int, default=200)
    ap.add_argument("--port",    type=int, default=5050)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data)
    app = create_app(data_dir, args.limit)

    if not args.no_open:
        Timer(1.0, lambda: webbrowser.open(f"http://localhost:{args.port}")).start()

    print(f"Curator running → http://localhost:{args.port}")
    print(f"Data dir: {data_dir.resolve()}")
    print("Ctrl+C to stop\n")
    app.run(port=args.port, debug=False)

if __name__ == "__main__":
    main()