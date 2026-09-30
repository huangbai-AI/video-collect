"""Local video-link store: SQLite + tiny HTTP receiver for in-page collectors.

Usage:
  python3 store.py serve [--port 8765] [--idle 900]   # receiver, auto-exits when idle
  python3 store.py stats                              # counts per platform/list
  python3 store.py export [--out PATH]                # full snapshot (default data/videos.csv)
  python3 store.py export-new [--out PATH]            # only videos never exported before
  python3 store.py export-history                      # prior batches and pending count
  python3 store.py mark-exported FILE                  # one-time import of an older CSV
  python3 store.py ingest PLATFORM LIST FILE          # ingest a JSON file ({items:[...]} or [...])
  python3 store.py known PLATFORM LIST [--n 30]       # recent vids as JSON (for CSP-blocked sites)
"""
import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

COLLECTOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collectors")
DATA_DIR = os.path.expanduser(os.environ.get("VC_DATA_DIR", "~/.local/share/video-collect"))
DB_PATH = os.path.join(DATA_DIR, "videos.db")
CSV_PATH = os.path.join(DATA_DIR, "videos.csv")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
PLATFORMS = {"douyin", "xhs", "instagram", "tiktok", "x"}
ALLOWED_ORIGINS = ("https://www.douyin.com", "https://www.xiaohongshu.com",
                   "https://www.instagram.com", "https://www.tiktok.com",
                   "https://x.com", "https://www.x.com",
                   "https://twitter.com", "https://www.twitter.com")
FIELDS = ("url", "type", "title", "author", "cover", "likes", "published_at")

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  platform TEXT NOT NULL,
  vid TEXT NOT NULL,
  url TEXT NOT NULL,
  lists TEXT NOT NULL,
  type TEXT, title TEXT, author TEXT, cover TEXT, likes TEXT, published_at TEXT,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  PRIMARY KEY (platform, vid)
);
CREATE TABLE IF NOT EXISTS export_batches (
  batch_id TEXT PRIMARY KEY,
  exported_at TEXT NOT NULL,
  file_path TEXT NOT NULL,
  row_count INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS export_log (
  platform TEXT NOT NULL,
  vid TEXT NOT NULL,
  batch_id TEXT NOT NULL,
  exported_at TEXT NOT NULL,
  PRIMARY KEY (platform, vid),
  FOREIGN KEY (batch_id) REFERENCES export_batches(batch_id)
);
"""


def connect(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def validate(payload):
    """Return (platform, list_name, items) or raise ValueError."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    platform, list_name, items = payload.get("platform"), payload.get("list"), payload.get("items")
    if platform not in PLATFORMS:
        raise ValueError(f"unknown platform: {platform!r}")
    if not isinstance(list_name, str) or not list_name:
        raise ValueError("list is required")
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    clean = []
    for it in items:
        if isinstance(it, dict) and it.get("vid") and it.get("url"):
            clean.append({"vid": str(it["vid"])[:64], **{f: _s(it.get(f)) for f in FIELDS}})
    return platform, list_name, clean


def _s(v):
    return None if v is None else str(v)[:500]


def ingest(conn, platform, list_name, items, now=None):
    """Upsert items; returns number of videos not seen before in this list."""
    now = now or time.strftime("%Y-%m-%d %H:%M:%S")
    new = 0
    for it in items:
        row = conn.execute("SELECT lists FROM videos WHERE platform=? AND vid=?",
                           (platform, it["vid"])).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO videos (platform, vid, url, lists, type, title, author, cover, likes,"
                " published_at, first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (platform, it["vid"], it["url"], list_name, *(it[f] for f in FIELDS[1:]), now, now))
            new += 1
            continue
        lists = row["lists"].split(",")
        if list_name not in lists:
            new += 1
            lists = lists + [list_name]
        conn.execute(
            "UPDATE videos SET lists=?, last_seen=?, url=?,"
            " title=COALESCE(?,title), author=COALESCE(?,author), cover=COALESCE(?,cover),"
            " likes=COALESCE(?,likes), type=COALESCE(?,type) WHERE platform=? AND vid=?",
            (",".join(lists), now, it["url"], it["title"], it["author"], it["cover"],
             it["likes"], it["type"], platform, it["vid"]))
    conn.commit()
    return new


def stats(conn):
    rows = conn.execute(
        "SELECT platform, lists, COUNT(*) n, SUM(first_seen >= date('now','localtime')) today"
        " FROM videos GROUP BY platform, lists ORDER BY platform").fetchall()
    return [dict(r) for r in rows]


def export_csv(conn, out=CSV_PATH):
    rows = conn.execute("SELECT * FROM videos ORDER BY first_seen DESC").fetchall()
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(rows[0].keys() if rows else ["platform", "vid", "url"])
        w.writerows([tuple(r) for r in rows])
    return out, len(rows)


def export_status(conn):
    total = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    exported = conn.execute("SELECT COUNT(*) FROM export_log").fetchone()[0]
    batches = [dict(row) for row in conn.execute(
        "SELECT batch_id, exported_at, file_path, row_count FROM export_batches"
        " ORDER BY exported_at DESC, batch_id DESC")]
    return {"total": total, "exported": exported, "pending": total - exported,
            "batches": batches}


def mark_exported_from_csv(conn, path):
    """Record a pre-existing CSV as already exported without changing the videos."""
    path = os.path.abspath(path)
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"platform", "vid"}.issubset(reader.fieldnames):
            raise ValueError("CSV needs platform and vid columns")
        keys = {(row["platform"], row["vid"]) for row in reader
                if row.get("platform") and row.get("vid")}
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()[:16]
    batch_id = "existing-" + digest
    exported_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("INSERT OR IGNORE INTO export_batches VALUES (?,?,?,0)",
                     (batch_id, exported_at, path))
        marked = 0
        missing = 0
        for platform, vid in sorted(keys):
            exists = conn.execute("SELECT 1 FROM videos WHERE platform=? AND vid=?",
                                  (platform, vid)).fetchone()
            if not exists:
                missing += 1
                continue
            result = conn.execute("INSERT OR IGNORE INTO export_log VALUES (?,?,?,?)",
                                  (platform, vid, batch_id, exported_at))
            marked += result.rowcount
        conn.execute("UPDATE export_batches SET row_count=? WHERE batch_id=?",
                     (conn.execute("SELECT COUNT(*) FROM export_log WHERE batch_id=?",
                                   (batch_id,)).fetchone()[0], batch_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"marked": marked, "already_recorded": len(keys) - marked - missing,
            "not_in_library": missing, "batch_id": batch_id}


def export_new_csv(conn, out=None, now=None):
    """Write only never-exported videos and record the batch; no file if none are new."""
    now = now or time.strftime("%Y-%m-%d %H:%M:%S")
    batch_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    out = os.path.abspath(out or os.path.join(EXPORT_DIR, f"videos-new-{batch_id}.csv"))
    tmp_path = None
    created_out = False
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = conn.execute(
            "SELECT v.* FROM videos v LEFT JOIN export_log e"
            " ON e.platform=v.platform AND e.vid=v.vid"
            " WHERE e.vid IS NULL ORDER BY v.first_seen, v.platform, v.vid"
        ).fetchall()
        if not rows:
            conn.commit()
            return None, 0
        if os.path.exists(out):
            raise FileExistsError(out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8-sig",
                                         dir=os.path.dirname(out), delete=False) as f:
            tmp_path = f.name
            writer = csv.writer(f)
            writer.writerow(rows[0].keys())
            writer.writerows([tuple(row) for row in rows])
        os.link(tmp_path, out)  # fails rather than overwriting an existing export
        created_out = True
        os.unlink(tmp_path)
        tmp_path = None
        conn.execute("INSERT INTO export_batches VALUES (?,?,?,?)",
                     (batch_id, now, out, len(rows)))
        conn.executemany("INSERT INTO export_log VALUES (?,?,?,?)",
                         [(row["platform"], row["vid"], batch_id, now) for row in rows])
        conn.commit()
        return out, len(rows)
    except Exception:
        conn.rollback()
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if created_out and os.path.exists(out):
            os.unlink(out)
        raise


def make_handler(conn, lock, touch):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            origin = self.headers.get("Origin")
            if origin in ALLOWED_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")

        def _json(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            touch()
            if self.path == "/ping":
                return self._json(200, {"ok": True})
            if self.path.startswith("/c/"):
                return self._collector(self.path[3:])
            if self.path == "/stats":
                with lock:
                    return self._json(200, {"ok": True, "data": stats(conn)})
            self._json(404, {"ok": False, "error": "not found"})

        def _collector(self, name):
            path = os.path.join(COLLECTOR_DIR, os.path.basename(name))
            if not name.endswith(".js") or not os.path.isfile(path):
                return self._json(404, {"ok": False, "error": "no such collector"})
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            touch()
            origin = self.headers.get("Origin")
            if origin is not None and origin not in ALLOWED_ORIGINS:
                return self._json(403, {"ok": False, "error": "origin not allowed"})
            if self.path != "/ingest":
                return self._json(404, {"ok": False, "error": "not found"})
            try:
                size = int(self.headers.get("Content-Length", 0))
                if size > 5_000_000:
                    raise ValueError("payload too large")
                platform, list_name, items = validate(json.loads(self.rfile.read(size)))
                with lock:
                    new = ingest(conn, platform, list_name, items)
                self._json(200, {"ok": True, "new": new, "received": len(items)})
            except (ValueError, json.JSONDecodeError) as e:
                self._json(400, {"ok": False, "error": str(e)})
            except Exception as e:  # keep receiver alive, report to caller
                sys.stderr.write(f"ingest error: {e!r}\n")
                self._json(500, {"ok": False, "error": "internal error"})

        def log_message(self, *args):
            pass

    return Handler


def serve(port, idle):
    conn, lock = connect(), threading.Lock()
    last = [time.time()]
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(conn, lock, lambda: last.__setitem__(0, time.time())))

    def watchdog():
        while time.time() - last[0] < idle:
            time.sleep(5)
        server.shutdown()

    threading.Thread(target=watchdog, daemon=True).start()
    print(f"receiver on http://127.0.0.1:{port} (idle exit {idle}s), db={DB_PATH}", flush=True)
    server.serve_forever()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--idle", type=int, default=900)
    sub.add_parser("stats")
    e = sub.add_parser("export")
    e.add_argument("--out", default=CSV_PATH)
    e_new = sub.add_parser("export-new")
    e_new.add_argument("--out")
    sub.add_parser("export-history")
    baseline = sub.add_parser("mark-exported")
    baseline.add_argument("file")
    i = sub.add_parser("ingest")
    i.add_argument("platform")
    i.add_argument("list")
    i.add_argument("file")
    k = sub.add_parser("known")
    k.add_argument("platform")
    k.add_argument("list")
    k.add_argument("--n", type=int, default=30)
    a = p.parse_args()
    if a.cmd == "serve":
        serve(a.port, a.idle)
    elif a.cmd == "stats":
        print(json.dumps(stats(connect()), ensure_ascii=False, indent=1))
    elif a.cmd == "ingest":
        with open(a.file, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", []) if isinstance(data, dict) else data
        platform, list_name, clean = validate({"platform": a.platform, "list": a.list, "items": items})
        print(json.dumps({"new": ingest(connect(), platform, list_name, clean), "received": len(clean)}))
    elif a.cmd == "known":
        rows = connect().execute(
            "SELECT vid FROM videos WHERE platform=? AND (',' || lists || ',') LIKE ?"
            " ORDER BY first_seen DESC LIMIT ?", (a.platform, f"%,{a.list},%", a.n)).fetchall()
        print(json.dumps([r["vid"] for r in rows]))
    elif a.cmd == "export-new":
        out, n = export_new_csv(connect(), a.out)
        print(json.dumps({"new": n, "path": out}, ensure_ascii=False))
    elif a.cmd == "export-history":
        print(json.dumps(export_status(connect()), ensure_ascii=False, indent=2))
    elif a.cmd == "mark-exported":
        print(json.dumps(mark_exported_from_csv(connect(), a.file), ensure_ascii=False))
    else:
        out, n = export_csv(connect(), a.out)
        print(f"exported {n} rows -> {out}")


if __name__ == "__main__":
    main()
