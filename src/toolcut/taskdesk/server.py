"""HTTP front for TaskDesk. Routes are built from ops.OPS. Binds to 127.0.0.1 only."""

from __future__ import annotations

import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from .db import DB, ApiError
from .ops import OPS, Op

MAX_BODY = 64 * 1024


def _route(op: Op) -> re.Pattern:
    pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", op.path)
    return re.compile("^" + pattern + "$")


ROUTES = [(op, _route(op)) for op in OPS]


def _coerce(param, raw):
    if raw is None:
        return None
    if param.type == "integer":
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ApiError(400, f"{param.name} must be an integer") from None
    if param.type == "integer_or_null":
        if raw in (None, "null"):
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ApiError(400, f"{param.name} must be an integer or null") from None
    if param.type == "boolean":
        if isinstance(raw, bool):
            return raw
        if str(raw).lower() in ("true", "1"):
            return True
        if str(raw).lower() in ("false", "0"):
            return False
        raise ApiError(400, f"{param.name} must be true or false")
    if not isinstance(raw, str):
        raise ApiError(400, f"{param.name} must be a string")
    return raw


def match(method: str, path: str):
    for op, rx in ROUTES:
        if op.method != method:
            continue
        m = rx.match(path)
        if m:
            return op, {k: unquote(v) for k, v in m.groupdict().items()}
    return None, None


def bind_args(op: Op, path_args: dict, query: dict, body: dict) -> dict:
    known = {p.name for p in op.params}
    extra = (set(body) | set(query)) - known
    if extra:
        raise ApiError(400, f"unknown parameter: {', '.join(sorted(extra))}")
    args = {}
    for p in op.params:
        source = {"path": path_args, "query": query, "body": body}[p.where]
        if p.name not in source or (source[p.name] is None and p.type != "integer_or_null"):
            if p.required:
                raise ApiError(400, f"missing required parameter {p.name}")
            continue
        args[p.name] = _coerce(p, source[p.name])
    return args


class TaskDeskServer:
    """Runs TaskDesk on 127.0.0.1 in a background thread. Use as a context manager."""

    def __init__(self, seed: int | None = None):
        self.db = DB() if seed is None else DB(seed)
        self.admin_token = secrets.token_hex(16)
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _handle(self, method):
                url = urlsplit(self.path)
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    if length > MAX_BODY:
                        raise ApiError(413, "body too large")
                    raw = self.rfile.read(length) if length else b""
                    if url.path.startswith("/_admin/"):
                        return self._admin(method, url.path)
                    op, path_args = match(method, url.path)
                    if op is None:
                        raise ApiError(404, f"no route for {method} {url.path}")
                    try:
                        body = json.loads(raw) if raw else {}
                    except json.JSONDecodeError:
                        raise ApiError(400, "body is not valid JSON") from None
                    if not isinstance(body, dict):
                        raise ApiError(400, "body must be a JSON object")
                    query = {k: v[-1] for k, v in parse_qs(url.query).items()}
                    args = bind_args(op, path_args, query, body)
                    self._send(200, server.db.call(op.name, args))
                except ApiError as e:
                    self._send(e.status, {"error": e.message})

            def _admin(self, method, path):
                if not secrets.compare_digest(self.headers.get("X-Admin-Token", ""), server.admin_token):
                    raise ApiError(403, "admin token required")
                if method == "GET" and path == "/_admin/dump":
                    d = server.db.dump()
                    return self._send(200, {"data": {t: list(rows.values()) for t, rows in d.items()}, "calls": list(server.db.calls)})
                if method == "POST" and path == "/_admin/reset":
                    server.db.reset()
                    return self._send(200, {"ok": True})
                raise ApiError(404, "no such admin route")

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

            def do_PATCH(self):
                self._handle("PATCH")

            def do_DELETE(self):
                self._handle("DELETE")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.host, self.port = self.httpd.server_address[:2]
        self.url = f"http://{self.host}:{self.port}"
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    def reset(self):
        self.db.reset()
