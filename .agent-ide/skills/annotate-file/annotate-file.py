#!/usr/bin/env python3
"""annotate-file — one instance per document; highlight a span, type what to change.

    annotate-file open --doc <path> [--id <id>]   create/refresh an instance, start the server, print its url
    annotate-file list                            instances on this machine, with the document each serves
    annotate-file url --id <id>                   print the url only
    annotate-file stop                            stop the server
    annotate-file serve                           run the server in the foreground

an instance is one json in this skill's `data/`: {"id", "doc", "created", "updated", "items"}.
one port serves every instance; the first path segment picks it: http://127.0.0.1:8765/<id>/
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
from urllib.parse import unquote, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DATA = os.path.join(HERE, "data")
PORT = 8765
BASE = "http://127.0.0.1:%d" % PORT
PIDFILE = os.path.join(DATA, ".server.pid")
LOGFILE = os.path.join(DATA, ".server.log")


def inst_path(i):
    return os.path.join(DATA, i + ".json")


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


def doc_lines(doc):
    p = os.path.join(ROOT, doc)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read().split("\n")


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
    raise SystemExit("annotate-file: server did not start, see " + LOGFILE)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _out(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _json(self, o, code=200):
        self._out(code, json.dumps(o, ensure_ascii=False))

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            rows = []
            if os.path.isdir(DATA):
                for fn in sorted(os.listdir(DATA)):
                    if fn.endswith(".json") and not fn.startswith("."):
                        it = load(fn[:-5]) or {}
                        rows.append('<li><a href="/%s/">%s</a> &nbsp; <code>%s</code> &nbsp; <b>%d</b></li>'
                                    % (it.get("id"), it.get("id"), it.get("doc"), len(it.get("items") or [])))
            body = ("<meta charset=utf-8><title>annotate</title>"
                    "<style>body{font:14px/1.8 ui-monospace,Menlo,monospace;background:#fcfcfa;"
                    "color:#1c1c1a;padding:28px}code{color:#8a8a84}b{color:#1a6b4a}"
                    "a{color:#1c1c1a;text-decoration:none;border-bottom:1px solid #ddd}</style>"
                    "<h3>instances</h3><ul>%s</ul>") % ("".join(rows) or "<li>none yet — run: annotate open --doc &lt;path&gt;</li>")
            return self._out(200, body, "text/html")
        m = re.match(r"^/api/([^/]+)/doc$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance " + m.group(1)}, 404)
            lines = doc_lines(inst["doc"])
            if lines is None:
                return self._json({"error": "no document " + inst["doc"]}, 404)
            return self._json({"id": inst["id"], "doc": inst["doc"], "lines": lines,
                               "items": inst.get("items") or []})
        seg = [s for s in path.split("/") if s]
        if len(seg) == 1 and load(seg[0]):
            return self._out(200, page_html(), "text/html")
        self._json({"error": "no route"}, 404)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        m = re.match(r"^/api/([^/]+)/save$", path)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance"}, 404)
            inst["items"] = body.get("items") or []
            save(inst)
            return self._json({"ok": True, "n": len(inst["items"])})
        m = re.match(r"^/api/([^/]+)/add$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance"}, 404)
            item = body.get("item") or {}
            if not item.get("note"):
                return self._json({"error": "empty note"}, 400)
            inst.setdefault("items", []).append(
                {"line": item.get("line"), "end": item.get("end"), "quote": item.get("quote") or "",
                 "note": item["note"], "at": datetime.now().isoformat(timespec="seconds")})
            save(inst)
            return self._json({"ok": True, "n": len(inst["items"])})
        m = re.match(r"^/api/([^/]+)/del$", path)
        if m:
            inst = load(m.group(1))
            if not inst:
                return self._json({"error": "no instance"}, 404)
            i = body.get("index")
            if isinstance(i, int) and 0 <= i < len(inst.get("items") or []):
                inst["items"].pop(i)
                save(inst)
            return self._json({"ok": True, "n": len(inst.get("items") or [])})
        self._json({"error": "no route"}, 404)


def cmd_open(a):
    doc = a.doc
    if os.path.isabs(doc):
        doc = os.path.relpath(doc, ROOT)
    if doc.startswith(".."):
        raise SystemExit("annotate-file: the document must sit inside " + ROOT)
    if doc_lines(doc) is None:
        raise SystemExit("annotate-file: no such document " + doc)
    i = a.id or os.path.splitext(os.path.basename(doc))[0]
    inst = load(i) or {"id": i, "doc": doc, "created": datetime.now().isoformat(timespec="seconds"), "items": []}
    inst["doc"] = doc
    save(inst)
    ensure_server()
    print(BASE + "/" + i + "/")


def cmd_list(_a):
    if not os.path.isdir(DATA):
        return
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json") or fn.startswith("."):
            continue
        it = load(fn[:-5]) or {}
        print("%-16s %-60s %d" % (it.get("id"), it.get("doc"), len(it.get("items") or [])))


def cmd_url(a):
    if not load(a.id):
        raise SystemExit("annotate-file: no instance " + a.id)
    print(BASE + "/" + a.id + "/")


def cmd_stop(_a):
    if not os.path.isfile(PIDFILE):
        print("annotate-file: no pid file")
        return
    pid = int(open(PIDFILE).read().strip() or 0)
    try:
        os.kill(pid, signal.SIGTERM)
        print("annotate-file: stopped %d" % pid)
    except ProcessLookupError:
        print("annotate-file: already stopped")
    os.remove(PIDFILE)


def cmd_serve(_a):
    os.makedirs(DATA, exist_ok=True)
    print("annotate-file: serving %s on port %d" % (ROOT, PORT), flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


def main():
    ap = argparse.ArgumentParser(prog="annotate-file")
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
