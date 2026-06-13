"""Tiny dependency-free mock for the FE auth contract (release 1.6).

Serves the ``/api/me`` and ``/api/me/recheck`` shapes from the recorded JSON
fixtures in this folder so the frontend can develop the denied/preview-blur and
onboarding flows WITHOUT a live Discord or the real backend.

Usage:
    MOCK_ACCESS_STATE=NO_DESK python mock_me_server.py 8787
    # then point the FE at http://localhost:8787

Env:
    MOCK_ACCESS_STATE   one of ANON | NO_DESK | DESK | GRACE   (default DESK)
    MOCK_RECHECK_STATE  state returned by POST /api/me/recheck  (default = MOCK_ACCESS_STATE)

Notes:
* Stdlib only (``http.server``); no FastAPI/uvicorn needed.
* Sends permissive, credentialed CORS headers so a cookie-bearing FE on
  http://localhost:3000 can call it.
* This is a DEV fixture, not the production server.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MOCK_DIR = Path(__file__).resolve().parent

_FIXTURES = {
    "ANON": "me_anon.json",
    "NO_DESK": "me_no_desk.json",
    "DESK": "me_desk.json",
    "GRACE": "me_grace.json",
}


def _load(state: str) -> dict:
    name = _FIXTURES.get(state.upper(), _FIXTURES["DESK"])
    return json.loads((MOCK_DIR / name).read_text(encoding="utf-8"))


def _me_state() -> str:
    return os.environ.get("MOCK_ACCESS_STATE", "DESK").upper()


def _recheck_state() -> str:
    return os.environ.get("MOCK_RECHECK_STATE", _me_state()).upper()


class Handler(BaseHTTPRequestHandler):
    server_version = "FlowDeskMockMe/1.6"

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "*")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._cors()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:  # (http.server API)
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/me":
            self._json(200, _load(_me_state()))
        elif path == "/api/health":
            self._json(200, {"status": "ok", "feed_mode": "mock", "version": "mock"})
        else:
            self._json(404, {"error": "not found", "code": "NOT_FOUND"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/me/recheck":
            state = _me_state()
            if state == "ANON":
                # recheck needs a session -> 401 when anonymous.
                self._json(401, {"error": "authentication required", "code": "UNAUTHENTICATED"})
            else:
                self._json(200, _load(_recheck_state()))
        elif path == "/api/auth/logout":
            self._json(204, {})
        else:
            self._json(404, {"error": "not found", "code": "NOT_FOUND"})

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("[mock_me] " + (fmt % args) + "\n")


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    sys.stderr.write(
        f"[mock_me] serving /api/me as {_me_state()} on http://localhost:{port}\n"
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
