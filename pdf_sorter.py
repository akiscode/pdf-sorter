#!/usr/bin/env python3
import os
import shutil
import argparse
import zipfile
import io
import json
from pathlib import Path
from urllib.parse import quote

from flask import Flask, request, redirect, url_for, render_template_string, send_from_directory, abort

APP_DIR = Path(__file__).resolve().parent
PDFJS_DIR = APP_DIR / "_pdfjs"
PDFJS_VIEWER = PDFJS_DIR / "web" / "viewer.html"
PDFJS_ZIP_URL = "https://github.com/mozilla/pdf.js/releases/download/v4.10.38/pdfjs-4.10.38-dist.zip"

RECENTS_FILE = APP_DIR / "_recent_folders.json"
MAX_RECENTS = 12

TEMPLATE = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PDF Sorter</title>
  <style>
    body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; background: #0f1115; color: #e6e6e6; }
    .wrap { display: grid; grid-template-columns: 360px 1fr; height: 100vh; }
    .sidebar { border-right: 1px solid #2a2f3a; padding: 14px; overflow: auto; background:#121521; }
    .main { display: flex; flex-direction: column; height: 100vh; }
    .topbar { padding: 10px 12px; border-bottom: 1px solid #2a2f3a; display:flex; gap:10px; align-items:center; background:#0f1115; flex-wrap: wrap; }
    .content { flex: 1; padding: 0; }
    .pdf { width: 100%; height: calc(100vh - 106px); border: 0; background: #0b0d11; } /* a bit taller topbar now */

    input, select, button {
      background: #171b27; color: #e6e6e6; border: 1px solid #2a2f3a;
      border-radius: 10px; padding: 8px 10px;
    }
    button { cursor: pointer; }
    button:hover { border-color: #4a5670; }

    .small { font-size: 12px; color: #aeb6c8; }
    .fileitem { padding: 8px 10px; border: 1px solid #2a2f3a; border-radius: 10px; margin: 8px 0; background:#0f1115; }
    .fileitem a { color: #cfe1ff; text-decoration: none; }
    .fileitem a:hover { text-decoration: underline; }
    .pill { display:inline-block; font-size: 12px; padding: 2px 8px; border: 1px solid #2a2f3a; border-radius: 999px; color:#aeb6c8; margin-left: 6px; }

    .row { display:flex; gap:10px; align-items:center; flex-wrap: wrap; }
    .grow { flex: 1; min-width: 240px; }
    .danger { border-color:#7a2c2c; }
    .danger:hover { border-color:#b54444; }
    code { color:#cfe1ff; }
    .hint { font-size: 11px; color:#95a0b8; margin-top: 4px; }
    .chips { display:flex; gap:8px; flex-wrap: wrap; align-items:center; }
    .chip {
      font-size: 12px;
      padding: 6px 10px;
      border: 1px solid #2a2f3a;
      border-radius: 999px;
      background: #141827;
      color: #cfe1ff;
      cursor: pointer;
      user-select: none;
      max-width: 360px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .chip:hover { border-color:#4a5670; }
    .chipLabel { color:#aeb6c8; font-size: 12px; margin-right: 4px; }
    .topbarBlock { display:flex; flex-direction: column; gap: 6px; width: 100%; }
  </style>
</head>
<body>
<div class="wrap">
  <div class="sidebar">
    <div class="row" style="justify-content:space-between;">
      <div><strong>PDF Sorter</strong></div>
      <div class="pill">{{ idx + 1 }} / {{ total }}</div>
    </div>

    <div class="small" style="margin-top:6px;">
      Root: <code>{{ root }}</code><br/>
      PDFs only, non-recursive
    </div>

    <hr style="border:0;border-top:1px solid #2a2f3a;margin:12px 0;"/>

    <div class="small">
      <strong>Keyboard</strong><br/>
      j / → = next<br/>
      k / ← = prev<br/>
      r = focus rename<br/>
      m = focus move folder box
    </div>

    <hr style="border:0;border-top:1px solid #2a2f3a;margin:12px 0;"/>

    <div class="small"><strong>Queue</strong></div>
    {% for f in files[:80] %}
      {% set i = loop.index0 %}
      <div class="fileitem" style="{% if i==idx %}border-color:#5a78ff{% endif %}">
        <a href="{{ url_for('index', i=i) }}">{{ f }}</a>
        {% if i==idx %}<span class="pill">current</span>{% endif %}
      </div>
    {% endfor %}
  </div>

  <div class="main">
    <div class="topbar">
      <div class="topbarBlock">
        <div class="row">
          <form method="post" action="{{ url_for('rename') }}" class="row" style="margin:0;">
            <input type="hidden" name="i" value="{{ idx }}">
            <input id="renameBox" class="grow" name="new_name" value="{{ current }}">
            <button type="submit">Rename</button>
          </form>

          <form method="post" action="{{ url_for('move') }}" class="row" style="margin:0;">
            <input type="hidden" name="i" value="{{ idx }}">
            <select name="dest_preset">
              {% for d in dests %}
                <option value="{{ d }}">{{ d }}</option>
              {% endfor %}
            </select>
            <input id="moveCustom" name="dest_custom" placeholder="or type folder (e.g. Bills/2026)" style="min-width:240px;">
            <button type="submit">Move</button>
            <div class="hint">Relative to root</div>
          </form>

          <a href="{{ url_for('index', i=prev_i) }}"><button type="button">Prev</button></a>
          <a href="{{ url_for('index', i=next_i) }}"><button type="button">Next</button></a>

          <form method="post" action="{{ url_for('trash') }}" style="margin-left:auto;">
            <input type="hidden" name="i" value="{{ idx }}">
            <button class="danger" type="submit">Trash</button>
          </form>
        </div>

        <div class="row" style="justify-content:space-between;">
          <div class="chips">
            <span class="chipLabel">Recent folders:</span>
            {% if recents and recents|length > 0 %}
              {% for rf in recents %}
                <span class="chip" data-folder="{{ rf }}" title="{{ rf }}">{{ rf }}</span>
              {% endfor %}
            {% else %}
              <span class="small">(none yet)</span>
            {% endif %}
          </div>

          {% if recents and recents|length > 0 %}
          <form method="post" action="{{ url_for('clear_recents') }}" style="margin:0;">
            <button type="submit" title="Clear recent folder chips">Clear recents</button>
          </form>
          {% endif %}
        </div>
      </div>
    </div>

    <div class="content">
      {% if current %}
        <iframe class="pdf" src="{{ viewer_url }}"></iframe>
      {% else %}
        <div style="padding:16px;">No PDFs found.</div>
      {% endif %}
    </div>
  </div>
</div>

<script>
document.addEventListener('keydown', (e) => {
  const tag = e.target.tagName.toLowerCase();
  if (['input','select','textarea'].includes(tag)) return;

  if (e.key === 'j' || e.key === 'ArrowRight') {
    e.preventDefault(); e.stopPropagation();
    location.href = "{{ url_for('index', i=next_i) }}";
  }
  if (e.key === 'k' || e.key === 'ArrowLeft') {
    e.preventDefault(); e.stopPropagation();
    location.href = "{{ url_for('index', i=prev_i) }}";
  }
  if (e.key === 'r' || e.key === 'R') {
    e.preventDefault(); e.stopPropagation();
    const b = document.getElementById('renameBox');
    b.focus(); b.select();
  }
  if (e.key === 'm' || e.key === 'M') {
    e.preventDefault(); e.stopPropagation();
    const b = document.getElementById('moveCustom');
    b.focus(); b.select();
  }
});

// Click a chip -> populate custom folder box (no auto-move)
document.querySelectorAll('.chip').forEach((el) => {
  el.addEventListener('click', () => {
    const folder = el.getAttribute('data-folder') || '';
    const input = document.getElementById('moveCustom');
    input.value = folder;
    input.focus();
    input.select();
  });
});
</script>
</body>
</html>
"""

def list_pdfs(root: Path):
    return sorted(p.name for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")

def safe_filename(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Empty filename")
    if any(c in name for c in r'\/'):
        raise ValueError("Invalid filename")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name

def sanitize_rel_folder(folder: str) -> Path:
    folder = folder.strip().replace("\\", "/")
    if not folder:
        raise ValueError("Empty folder name")
    if folder.startswith("/") or folder.startswith("\\\\") or ":" in folder:
        raise ValueError("Folder must be relative to root (not an absolute path)")
    parts = [p for p in folder.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError("Folder cannot contain '..'")
    parts = [p for p in parts if p != "."]
    if not parts:
        raise ValueError("Invalid folder name")
    return Path(*parts)

def ensure_dest(root: Path, rel_folder: str) -> Path:
    rel = sanitize_rel_folder(rel_folder)
    dest = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        dest.relative_to(root_resolved)
    except ValueError:
        raise ValueError("Destination must stay within root folder")
    dest.mkdir(parents=True, exist_ok=True)
    return dest

def ensure_pdfjs_installed():
    if PDFJS_VIEWER.exists():
        return
    print("PDF.js not found; downloading…")
    import urllib.request
    with urllib.request.urlopen(PDFJS_ZIP_URL) as resp:
        data = resp.read()

    tmp = APP_DIR / "_pdfjs_tmp"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(tmp)

    viewer = None
    for p in tmp.rglob("viewer.html"):
        if p.parent.name == "web":
            viewer = p
            break
    if viewer is None:
        viewer = next(iter(tmp.rglob("viewer.html")), None)
    if viewer is None:
        raise RuntimeError("Could not find viewer.html in the downloaded zip.")

    candidate_root = viewer.parent.parent  # web/.. is pdfjs root

    if PDFJS_DIR.exists():
        shutil.rmtree(PDFJS_DIR)
    shutil.move(str(candidate_root), str(PDFJS_DIR))
    shutil.rmtree(tmp, ignore_errors=True)

    if not PDFJS_VIEWER.exists():
        raise RuntimeError(f"PDF.js installed but viewer not found at {PDFJS_VIEWER}")

    print(f"Installed PDF.js into: {PDFJS_DIR}")

def load_recents() -> list[str]:
    try:
        if RECENTS_FILE.exists():
            data = json.loads(RECENTS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out = []
                for x in data:
                    if isinstance(x, str) and x.strip():
                        out.append(x.strip())
                # de-dupe preserving order
                seen = set()
                deduped = []
                for x in out:
                    if x not in seen:
                        seen.add(x)
                        deduped.append(x)
                return deduped[:MAX_RECENTS]
    except Exception:
        pass
    return []

def save_recents(recents: list[str]) -> None:
    try:
        RECENTS_FILE.write_text(json.dumps(recents[:MAX_RECENTS], indent=2), encoding="utf-8")
    except Exception:
        # non-fatal
        pass

def bump_recent(folder: str) -> None:
    folder = folder.strip().replace("\\", "/")
    if not folder:
        return
    recents = load_recents()
    recents = [x for x in recents if x != folder]
    recents.insert(0, folder)
    save_recents(recents)

def create_app(root: Path, dests):
    ensure_pdfjs_installed()
    app = Flask(__name__)

    @app.get("/")
    def index():
        files = list_pdfs(root)
        total = len(files)
        idx = 0
        if total:
            try:
                idx = int(request.args.get("i", 0))
            except ValueError:
                idx = 0
            idx = max(0, min(idx, total - 1))

        current = files[idx] if files else None
        if current:
            pdf_url = url_for("file", name=current)
            viewer_url = url_for("pdfjs_viewer") + "?file=" + quote(pdf_url)
        else:
            viewer_url = ""

        recents = load_recents()

        return render_template_string(
            TEMPLATE,
            root=str(root),
            files=files,
            total=total,
            idx=idx,
            current=current,
            viewer_url=viewer_url,
            prev_i=max(idx - 1, 0),
            next_i=min(idx + 1, max(total - 1, 0)),
            dests=dests,
            recents=recents,
        )

    @app.get("/file/<path:name>")
    def file(name):
        if "/" in name or "\\" in name:
            abort(400)
        path = root / name
        if not path.exists() or path.suffix.lower() != ".pdf":
            abort(404)
        return send_from_directory(root, name, mimetype="application/pdf", as_attachment=False)

    @app.get("/viewer/web/viewer.html")
    def pdfjs_viewer():
        return send_from_directory(PDFJS_DIR / "web", "viewer.html")

    @app.get("/viewer/<path:subpath>")
    def pdfjs_assets(subpath):
        return send_from_directory(PDFJS_DIR, subpath)

    @app.post("/clear_recents")
    def clear_recents():
        save_recents([])
        # return to where you were (best effort)
        i = request.args.get("i")
        return redirect(url_for("index", i=i) if i is not None else url_for("index"))

    @app.post("/rename")
    def rename():
        files = list_pdfs(root)
        if not files:
            return redirect(url_for("index"))

        idx = int(request.form["i"])
        idx = max(0, min(idx, len(files) - 1))
        old = files[idx]
        new = safe_filename(request.form["new_name"])

        old_path = root / old
        new_path = root / new

        if new_path.exists() and new_path.name != old_path.name:
            return "Rename failed: target already exists.", 400

        old_path.rename(new_path)
        return redirect(url_for("index", i=idx))

    @app.post("/move")
    def move():
        files = list_pdfs(root)
        if not files:
            return redirect(url_for("index"))

        idx = int(request.form["i"])
        idx = max(0, min(idx, len(files) - 1))
        name = files[idx]

        dest_custom = (request.form.get("dest_custom") or "").strip()
        dest_preset = (request.form.get("dest_preset") or "").strip()
        dest_name = dest_custom if dest_custom else dest_preset
        if not dest_name:
            return "Move failed: no destination provided.", 400

        try:
            dest = ensure_dest(root, dest_name)
        except ValueError as e:
            return f"Move failed: {e}", 400

        src = root / name
        dst = dest / name
        if dst.exists():
            return "Move failed: file already exists in destination.", 400

        shutil.move(str(src), str(dst))

        # Persist recent folder chip
        bump_recent(dest_name)

        remaining = list_pdfs(root)
        if not remaining:
            return redirect(url_for("index", i=0))
        return redirect(url_for("index", i=min(idx, len(remaining) - 1)))

    @app.post("/trash")
    def trash():
        files = list_pdfs(root)
        if not files:
            return redirect(url_for("index"))

        idx = int(request.form["i"])
        idx = max(0, min(idx, len(files) - 1))
        name = files[idx]

        dest = ensure_dest(root, "_trash")
        src = root / name
        dst = dest / name
        if dst.exists():
            return "Trash failed: file already exists in _trash.", 400

        shutil.move(str(src), str(dst))

        remaining = list_pdfs(root)
        if not remaining:
            return redirect(url_for("index", i=0))
        return redirect(url_for("index", i=min(idx, len(remaining) - 1)))

    return app

def main():
    ap = argparse.ArgumentParser(description="Local PDF preview/rename/move web app (same-origin PDF.js).")
    ap.add_argument("folder", help="Folder containing PDFs (non-recursive).")
    ap.add_argument("--port", type=int, default=5055)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--dests", default="_sorted,_keep,_review", help="Comma-separated destination folders (presets).")
    args = ap.parse_args()

    root = Path(os.path.expanduser(args.folder)).resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"Not a folder: {root}")

    dests = [d.strip() for d in args.dests.split(",") if d.strip()]
    app = create_app(root, dests)

    print(f"Serving {root}")
    print(f"Open: http://{args.host}:{args.port}/")
    app.run(args.host, args.port, debug=False)

if __name__ == "__main__":
    main()
