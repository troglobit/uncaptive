#!/usr/bin/env python3
# SPDX-License-Identifier: ISC
"""Fake Icomera and Oxyfi portals; runs uncaptive against them."""
import json, os, subprocess, sys, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "..", "uncaptive")


class Portal(BaseHTTPRequestHandler):
    mode = "icomera"
    authed = False
    log_lines = []

    def log_message(self, fmt, *a):
        Portal.log_lines.append(fmt % a)

    def send(self, code, body="", ctype="text/html", loc=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if loc:
            self.send_header("Location", loc)
        self.end_headers()
        self.wfile.write(body.encode())

    def jsonp(self, obj):
        self.send(200, "cb(%s);" % json.dumps(obj), "application/javascript")

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        base = "http://%s" % self.headers["Host"]
        if u.path == "/probe":
            if Portal.authed:
                return self.send(204)
            if Portal.mode == "icomera":
                return self.send(302, loc=base + "/portal/?url=" + urllib.parse.quote(base + "/probe"))
            return self.send(302, loc=base + "/oxyfi/?pushedFrom=" + urllib.parse.quote(base + "/probe"))
        # --- Icomera ---
        if u.path == "/api/jsonp/user/":
            return self.jsonp({"authenticated": "1" if Portal.authed else "0", "ip": "10.1.1.2"})
        if u.path == "/hotspot/hotspot.cgi":
            assert q.get("method") == "login" and q.get("url") and q.get("onerror"), q
            Portal.authed = True
            return self.send(302, loc=q["url"] + "&status=0")
        # --- Oxyfi ---
        if u.path == "/oxyfi/":
            return self.send(200, "<html><script>var beUrl = 'x';var nodeUrl = 'y';"
                                  "var portalName = 'tib';</script></html>")
        if u.path == "/node/nodeCmd":
            rt = q.get("RequestType")
            if rt == "400201":
                return self.jsonp({"Result": 1000, "Data": "D" * 170, "NodeId": "node-1"})
            if rt == "400005":
                if q.get("Data") == "login-token":
                    Portal.authed = True
                    return self.jsonp({"Result": 1000, "Used": 0, "VoucherId": 7})
                return self.jsonp({"Result": 3000, "Used": 0, "VoucherId": 0})
            return self.jsonp({"Error": True})
        if u.path == "/be/beCmd.php":
            p = json.loads(q["params"])
            ev = p["Event"]
            assert p.get("ClientId") and p.get("ClientTime"), p
            Portal.log_lines.append("BE event %s state=%s" % (ev, p.get("State")))
            if ev == "getConfiguration":
                assert p.get("operator") == "tib", p
                return self.jsonp({"ClientData": "cd-1"})
            assert p.get("ClientData") == "cd-1", p
            if ev == "initiate":
                assert p.get("NodeId") == "node-1" and len(p.get("InitiateData", "")) == 170, p
                return self.jsonp({"State": "A6"})
            if ev == "acceptTerms":
                assert p["State"] == "A6"
                return self.jsonp({"State": "A5"})
            if ev == "setupRequest":
                assert p["State"] == "A5"
                return self.jsonp({"State": "S1", "QueueAction": "OX:400005", "Data": "login-token"})
            if ev == "setState":
                return self.jsonp({})
            return self.jsonp({"State": "I1"})
        self.send(404, "nope")


def run(mode, extra=()):
    Portal.mode, Portal.authed, Portal.log_lines = mode, False, []
    srv = HTTPServer(("127.0.0.1", 0), Portal)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    base = "http://127.0.0.1:%d" % srv.server_port
    cmd = [sys.executable, TOOL, "-v", "--retries", "1", "--probe", base + "/probe",
           "--base", base, "--handler", mode] + list(extra)
    r = subprocess.run(cmd, capture_output=True, text=True)
    srv.shutdown()
    return r, Portal.authed


def main():
    fails = 0
    for mode in ("icomera", "oxyfi"):
        r, authed = run(mode)
        ok = r.returncode == 0 and authed
        print("%-8s rc=%d authed=%s %s" % (mode, r.returncode, authed, "PASS" if ok else "FAIL"))
        if not ok or "-v" in sys.argv:
            print(r.stderr); print("\n".join(Portal.log_lines))
        fails += not ok
    # already online: must not touch anything and exit 0
    Portal.authed = True
    srv = HTTPServer(("127.0.0.1", 0), Portal)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    r = subprocess.run([sys.executable, TOOL, "--retries", "1",
                        "--probe", "http://127.0.0.1:%d/probe" % srv.server_port],
                       capture_output=True, text=True)
    srv.shutdown()
    ok = r.returncode == 0 and "no captive portal" in r.stderr
    print("%-8s rc=%d %s" % ("online", r.returncode, "PASS" if ok else "FAIL")); fails += not ok
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
