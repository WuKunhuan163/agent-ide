#!/usr/bin/env python3
"""annotate-pdf — one instance per pdf; drag a box, type what to change.

    annotate-pdf open --doc <path.pdf> [--id <id>]   create or refresh an instance, start the server, print its url
    annotate-pdf list                                instances, with the document and page count
    annotate-pdf url --id <id>                       print the url only
    annotate-pdf stop                                stop the server
    annotate-pdf serve                               run the server in the foreground

an instance is one json in this skill's `data/`:
  {"id", "doc", "pages", "created", "updated",
   "items": [{"page": 3, "rects": [{"x":0.12,"y":0.30,"w":0.4,"h":0.05}], "note": "...", "at": "..."}]}

**coordinates are relative to the page**, 0..1 from the top-left corner, so an item survives a
different zoom, a different browser, and a re-render at another dpi. that is what `line` is to
`annotate-file`.

rendered pages are cached next to the json, under `data/<id>/p<NN>.png`; they are thrown away and
made again when the pdf is newer than the cache.
"""

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
PORT = 8766
BASE = "http://127.0.0.1:%d" % PORT
PIDFILE = os.path.join(DATA, ".server.pid")
LOGFILE = os.path.join(DATA, ".server.log")
DPI = 120


def doc_path(doc):
    return os.path.join(ROOT, doc)


def inst_path(i):
    return os.path.join(DATA, i + ".json")


def cache_dir(i):
    return os.path.join(DATA, i)


def load(i):
    p = inst_path(i)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(inst):
    os.makedirs(DATA, exist_ok=True)
    inst["updated"] = datetime.now().isoformat(timespec="seconds")
    p = inst_path(inst["id"])
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(inst, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def open_pdf(doc):
    import pymupdf
    return pymupdf.open(doc_path(doc))


def page_png(inst, n):
    out = os.path.join(cache_dir(inst["id"]), "p%03d.png" % n)
    src = doc_path(inst["doc"])
    if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(src):
        with open(out, "rb") as f:
            return f.read()
    os.makedirs(cache_dir(inst["id"]), exist_ok=True)
    with open_pdf(inst["doc"]) as pdf:
        page = pdf[n - 1]
        pix = page.get_pixmap(dpi=DPI)
        pix.save(out)
    with open(out, "rb") as f:
        return f.read()


def page_size(inst):
    with open_pdf(inst["doc"]) as pdf:
        return [{"n": k + 1,
                 "w": round(p.rect.width * DPI / 72.0),
                 "h": round(p.rect.height * DPI / 72.0)} for k, p in enumerate(pdf)]



def _git(*args, cwd=None):
    p = subprocess.run(["git", "-C", cwd or ROOT, *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def repo_of(path):
    rc, out, _ = _git("rev-parse", "--show-toplevel", cwd=os.path.dirname(path) or ROOT)
    return out if rc == 0 else ""


def sync_before_serve(doc):
    """Commit whatever is uncommitted in `doc` and return the commit before it.

    The baseline is what the page measures against: every page whose text differs
    from that commit is painted, so the reader sees the change rather than a claim
    about it. A PDF that git does not track returns "" and the page falls back to
    the signature taken when it was opened.
    """
    p = doc_path(doc)
    root = repo_of(p)
    if not root:
        return ""
    rel = os.path.relpath(p, root)
    rc, status, _ = _git("status", "--porcelain", "--", rel, cwd=root)
    dirty = rc == 0 and bool(status.strip())
    if dirty:
        _git("add", "--", rel, cwd=root)
        _git("commit", "-m", "annotate: %s before serve" % doc, "--", rel, cwd=root)
        rc, base, _ = _git("rev-parse", "HEAD~1", cwd=root)
    else:
        rc, base, _ = _git("rev-parse", "HEAD", cwd=root)
    return base if rc == 0 else ""


def page_sig(stream):
    """One short hash per page, taken from the text layer."""
    import hashlib
    out = []
    import pymupdf
    with pymupdf.open(stream=stream, filetype="pdf") as pdf:
        for i in range(pdf.page_count):
            t = pdf[i].get_text().strip()
            out.append(hashlib.sha1(t.encode("utf-8", "replace")).hexdigest()[:12])
    return out


def changed_pages(inst):
    """Pages whose text moved since the baseline, plus the reason when it cannot be told."""
    cur = doc_path(inst["doc"])
    if not os.path.isfile(cur):
        return [], "missing"
    now = page_sig(open(cur, "rb").read())
    base = inst.get("baseline") or ""
    if base:
        root = repo_of(cur)
        rel = os.path.relpath(cur, root) if root else ""
        blob = b""
        if root and rel:
            r = subprocess.run(["git", "-C", root, "cat-file", "blob", "%s:%s" % (base, rel)],
                               capture_output=True)
            if r.returncode == 0:
                blob = r.stdout
        if blob:
            old = page_sig(blob)
            if len(old) == len(now):
                return [i + 1 for i, (a, b) in enumerate(zip(old, now)) if a != b], "git:" + base[:8]
    sig = inst.get("sig") or []
    if sig and len(sig) == len(now):
        return [i + 1 for i, (a, b) in enumerate(zip(sig, now)) if a != b], "signature"
    return [], "no baseline"

def page_text(inst, n):
    out = []
    with open_pdf(inst["doc"]) as pdf:
        page = pdf[n - 1]
        pw, ph = page.rect.width, page.rect.height
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                spans = line.get("spans") or []
                text = "".join(s.get("text", "") for s in spans)
                if not text.strip():
                    continue
                x0, y0, x1, y1 = line["bbox"]
                size = max((s.get("size", 0) for s in spans), default=0)
                font = (spans[0].get("font") or "") if spans else ""
                out.append({"x": round(x0 / pw, 4), "y": round(y0 / ph, 4),
                            "w": round((x1 - x0) / pw, 4), "h": round((y1 - y0) / ph, 4),
                            "size": round(size / ph, 4), "font": font.split("+")[-1],
                            "text": text})
    return out


def page_html():
    with open(os.path.join(HERE, "page.html"), encoding="utf-8") as f:
        return f.read()


def uptodate():
    with socket.socket() as s:
        s.settimeout(0.25)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def ensure_server():
    if uptodate():
        return
    os.makedirs(DATA, exist_ok=True)
    with open(LOGFILE, "ab") as log:
        p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "serve"],
                             stdout=log, stderr=log, start_new_session=True)
    with open(PIDFILE, "w") as f:
        f.write(str(p.pid))
    for _ in range(50):
        if uptodate():
            return
        time.sleep(0.1)
    raise SystemExit("annotate-pdf: server did not start, see " + LOGFILE)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _out(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, o, code=200):
        self._out(code, json.dumps(o, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            rows = []
            if os.path.isdir(DATA):
                for fn in sorted(os.listdir(DATA)):
                    if fn.endswith(".json") and not fn.startswith("."):
                        it = load(fn[:-5]) or {}
                        rows.append('<li><a href="/%s/">%s</a> &nbsp; <code>%s</code> &nbsp; %s pages &nbsp; <b>%d</b></li>'
                                    % (it.get("id"), it.get("id"), it.get("doc"), it.get("pages"),
                                       len(it.get("items") or [])))
            body = ("<meta charset=utf-8><title>annotate-pdf</title>"
                    "<style>body{font:14px/1.8 ui-monospace,Menlo,monospace;background:#fcfcfa;"
                    "color:#1c1c1a;padding:28px}code{color:#8a8a84}b{color:#1a6b4a}"
                    "a{color:#1c1c1a;text-decoration:none;border-bottom:1px solid #ddd}</style>"
                    "<h3>instances</h3><ul>%s</ul>") % ("".join(rows) or "<li>none yet — run: annotate-pdf open --doc &lt;path.pdf&gt;</li>")
            return self._out(200, body.encode(), "text/html; charset=utf-8")
        m = re.match(r"^/api/([^/]+)/doc$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance " + m.group(1)}, 404)
            try:
                sizes = page_size(inst)
            except Exception as e:
                return self._json({"error": "cannot read pdf: %s" % e}, 500)
            try:
                ch, why = changed_pages(inst)
            except Exception:
                ch, why = [], "unreadable"
            return self._json({"id": inst["id"], "doc": inst["doc"], "pages": sizes,
                               "items": inst.get("items") or [],
                               "baseline": inst.get("baseline") or "",
                               "changed_pages": ch, "changed_basis": why,
                               "mtime": os.stat(doc_path(inst["doc"])).st_mtime_ns})
        m = re.match(r"^/api/([^/]+)/text$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance"}, 404)
            q = parse_qs(urlparse(self.path).query)
            try:
                n = int((q.get("p") or ["1"])[0])
                return self._json({"p": n, "lines": page_text(inst, n)})
            except Exception as e:
                return self._json({"error": "no text layer: %s" % e}, 500)
        m = re.match(r"^/([^/]+)/p/(\d+)\.png$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance"}, 404)
            n = int(m.group(2))
            if not (1 <= n <= inst.get("pages", 0)):
                return self._json({"error": "no page %d" % n}, 404)
            try:
                return self._out(200, page_png(inst, n), "image/png")
            except Exception as e:
                return self._json({"error": "render failed: %s" % e}, 500)
        seg = [s for s in path.split("/") if s]
        if len(seg) == 1 and load(seg[0]):
            b = page_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(b)
            return
        self._json({"error": "no route"}, 404)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        inst = None
        m = re.match(r"^/api/([^/]+)/(save|add|del|upd)$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance"}, 404)
        if not inst:
            return self._json({"error": "no route"}, 404)
        act = m.group(2)
        if act == "save":
            inst["items"] = body.get("items") or []
        elif act == "add":
            item = body.get("item") or {}
            if not item.get("note"):
                return self._json({"error": "empty note"}, 400)
            rects = [{"x": round(float(r["x"]), 4), "y": round(float(r["y"]), 4),
                      "w": round(float(r["w"]), 4), "h": round(float(r["h"]), 4)}
                     for r in (item.get("rects") or []) if r]
            inst.setdefault("items", []).append(
                {"page": int(item.get("page") or 1), "rects": rects,
                 "quote": (item.get("quote") or "")[:300],
                 "note": item["note"], "at": datetime.now().isoformat(timespec="seconds")})
        elif act == "upd":
            i = body.get("index")
            note = (body.get("note") or "").strip()
            items = inst.get("items") or []
            if not (isinstance(i, int) and 0 <= i < len(items) and note):
                return self._json({"error": "bad index or empty note"}, 400)
            items[i]["note"] = note
            items[i]["at"] = datetime.now().isoformat(timespec="seconds")
        else:
            i = body.get("index")
            if isinstance(i, int) and 0 <= i < len(inst.get("items") or []):
                inst["items"].pop(i)
        save(inst)
        return self._json({"ok": True, "n": len(inst.get("items") or [])})


def cmd_open(a):
    doc = a.doc
    if os.path.isabs(doc):
        doc = os.path.relpath(doc, ROOT)
    if doc.startswith(".."):
        raise SystemExit("annotate-pdf: the document must sit inside " + ROOT)
    if not os.path.isfile(doc_path(doc)):
        raise SystemExit("annotate-pdf: no such file " + doc)
    try:
        with open_pdf(doc) as pdf:
            pages = pdf.page_count
    except Exception as e:
        raise SystemExit("annotate-pdf: cannot open %s (%s)" % (doc, e))
    i = a.id or os.path.splitext(os.path.basename(doc))[0]
    inst = load(i) or {"id": i, "doc": doc, "created": datetime.now().isoformat(timespec="seconds"), "items": []}
    inst["doc"] = doc
    inst["pages"] = pages
    inst["baseline"] = sync_before_serve(doc)
    try:
        inst["sig"] = page_sig(open(doc_path(doc), "rb").read())
    except Exception:
        inst["sig"] = []
    save(inst)
    ensure_server()
    ch, why = changed_pages(inst)
    if ch:
        print("annotate-pdf: %d page(s) changed since %s" % (len(ch), why))
    else:
        print("annotate-pdf: nothing changed since %s" % (why if why else "open"))
    print(BASE + "/" + i + "/")


def cmd_list(_a):
    if not os.path.isdir(DATA):
        return
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json") or fn.startswith("."):
            continue
        it = load(fn[:-5]) or {}
        print("%-16s %-58s %3s pages  %d" % (it.get("id"), it.get("doc"), it.get("pages"),
                                             len(it.get("items") or [])))


def cmd_url(a):
    if not load(a.id):
        raise SystemExit("annotate-pdf: no instance " + a.id)
    print(BASE + "/" + a.id + "/")


def cmd_stop(_a):
    if not os.path.isfile(PIDFILE):
        print("annotate-pdf: no pid file")
        return
    pid = int(open(PIDFILE).read().strip() or 0)
    try:
        os.kill(pid, signal.SIGTERM)
        print("annotate-pdf: stopped %d" % pid)
    except ProcessLookupError:
        print("annotate-pdf: already stopped")
    os.remove(PIDFILE)


def cmd_serve(_a):
    os.makedirs(DATA, exist_ok=True)
    print("annotate-pdf: serving %s on port %d" % (ROOT, PORT), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


def main():
    ap = argparse.ArgumentParser(prog="annotate-pdf")
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open"); o.add_argument("--doc", required=True); o.add_argument("--id"); o.set_defaults(f=cmd_open)
    sub.add_parser("list").set_defaults(f=cmd_list)
    u = sub.add_parser("url"); u.add_argument("--id", required=True); u.set_defaults(f=cmd_url)
    sub.add_parser("stop").set_defaults(f=cmd_stop)
    sub.add_parser("serve").set_defaults(f=cmd_serve)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
