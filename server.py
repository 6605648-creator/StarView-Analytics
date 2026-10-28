"""Backend: REST API (/api/<name>?plan=..&city=..) + dashboard page. Python standard library only."""
import sqlite3, json, os, csv, io
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import queries

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path); f = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path.startswith("/api/"):
            name = u.path[5:]; db = sqlite3.connect("ott.db"); db.row_factory = sqlite3.Row
            try:
                if name == "at_risk.csv":
                    buf = io.StringIO(); w = csv.writer(buf)
                    w.writerow(["sub_id", "name", "city", "plan", "price", "last_watch", "days_idle", "score", "level"])
                    for r in queries._risk_rows(db, f):
                        if r["score"] >= 40: w.writerow([r[k] for k in ("sub_id", "name", "city", "plan", "price", "last_watch", "days_idle", "score", "level")])
                    return self.send(200, buf.getvalue().encode(), "text/csv", "attachment; filename=at_risk_subscribers.csv")
                if name not in queries.API: return self.send(404, b'{"error":"unknown endpoint"}', "application/json")
                return self.send(200, json.dumps(queries.API[name](db, f)).encode(), "application/json")
            except Exception as e:
                return self.send(500, json.dumps({"error": str(e)}).encode(), "application/json")
            finally: db.close()
        if u.path in ("/", "/index.html"): return self.send(200, open("static/index.html", "rb").read(), "text/html; charset=utf-8")
        self.send(404, b"Not found", "text/plain")
    def send(self, code, body, ctype, disp=None):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        if disp: self.send_header("Content-Disposition", disp)
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass

if __name__ == "__main__":
    if not os.path.exists("ott.db"): os.system("python3 seed_data.py")
    print("Dashboard running at http://localhost:8000  (Ctrl+C to stop)")
    ThreadingHTTPServer(("", 8000), H).serve_forever()
