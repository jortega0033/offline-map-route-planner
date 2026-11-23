"""HTTP server (stdlib only), bound to 127.0.0.1."""

import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, fixture, routing
from .store import Store, StoreError, TitleExists, prepare_data_dir

HOST = "127.0.0.1"
MAX_BODY = 4096
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Fixed allowlist: request path -> (file name inside STATIC_DIR, content type).
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/tokens.css": ("tokens.css", "text/css; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

CSP = (
    "default-src 'self'; style-src 'self'; script-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; form-action 'none'"
)

ROUTE_ID_RE = re.compile(r"/api/v1/routes/([0-9]{1,18})")
JSON_TYPE = "application/json; charset=utf-8"


class ApiError(Exception):
    def __init__(self, status, code, message, headers=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


def validate_ids(body, allowed_keys):
    """Return body if it has exactly `allowed_keys` and valid from/to strings."""
    if set(body) != set(allowed_keys):
        raise ApiError(400, "validation", "Body must contain exactly: " + ", ".join(sorted(allowed_keys)))
    for key in ("from", "to"):
        v = body[key]
        if not isinstance(v, str) or not 1 <= len(v) <= 64:
            raise ApiError(400, "validation", f"'{key}' must be a string of 1 to 64 characters")


def validate_title(value):
    if not isinstance(value, str):
        raise ApiError(400, "validation", "'title' must be a string")
    title = unicodedata.normalize("NFC", value).strip()
    if not 1 <= len(title) <= 80:
        raise ApiError(400, "validation", "'title' must be 1 to 80 characters")
    for ch in title:
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs", "Zl", "Zp"):
            raise ApiError(400, "validation", "'title' must not contain control characters")
    return title


class Handler(BaseHTTPRequestHandler):
    server_version = "OfflineRoutes/" + __version__
    sys_version = ""
    protocol_version = "HTTP/1.0"
    timeout = 10

    # ---- plumbing -------------------------------------------------------
    def log_message(self, format, *args):  # noqa: A002
        pass

    def _send(self, status, body, content_type, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj, extra=None):
        data = json.dumps(obj, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self._send(status, data, JSON_TYPE, extra)

    def _error(self, status, code, message, extra=None):
        self._json(status, {"error": {"code": code, "message": message}}, extra)

    def send_error(self, code, message=None, explain=None):
        # Malformed requests rejected by http.server itself: keep JSON shape.
        self.close_connection = True
        text = {400: "Bad request", 414: "Request URI too long", 431: "Headers too large"}.get(
            code, "Request error"
        )
        err_code = "method_not_implemented" if code == 501 else "bad_request"
        try:
            self._error(code, err_code, text)
        except OSError:
            pass

    # ---- verbs ----------------------------------------------------------
    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = lambda self: self._dispatch(self.command)

    def _dispatch(self, method):
        self.close_connection = True
        self._body_consumed = False
        try:
            self._handle(method)
        except ApiError as e:
            self._drain_small_body()
            self._error(e.status, e.code, e.message, e.headers)
        except (ConnectionError, TimeoutError):
            pass
        except Exception:
            try:
                self._error(500, "internal", "Internal server error")
            except Exception:
                pass

    # ---- checks ---------------------------------------------------------
    def _allowed_hosts(self):
        port = self.server.server_address[1]
        return {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _check_host(self):
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in self._allowed_hosts():
            raise ApiError(403, "forbidden_host", "Host header not allowed")

    def _check_origin(self):
        origin = self.headers.get("Origin")
        if origin is None:
            return
        allowed = {"http://" + h for h in self._allowed_hosts()}
        if origin.strip().lower() not in allowed:
            raise ApiError(403, "forbidden_origin", "Origin not allowed")

    def _drain_small_body(self):
        """Read an unread, honestly-sized small body so closing the socket does
        not reset the connection before the client reads our error response."""
        if self._body_consumed:
            return
        self._body_consumed = True
        length = (self.headers.get("Content-Length") or "").strip()
        if re.fullmatch(r"[0-9]{1,4}", length) and 0 < int(length) <= MAX_BODY:
            try:
                self.rfile.read(int(length))
            except OSError:
                pass

    def _read_body_object(self):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
        if self.headers.get("Transfer-Encoding") is not None:
            raise ApiError(411, "length_required", "Content-Length is required")
        length = self.headers.get("Content-Length")
        if length is None:
            raise ApiError(411, "length_required", "Content-Length is required")
        if not re.fullmatch(r"[0-9]{1,30}", length.strip()):
            raise ApiError(400, "bad_request", "Invalid Content-Length")
        n = int(length.strip())
        if n > MAX_BODY:
            raise ApiError(413, "too_large", f"Body must be at most {MAX_BODY} bytes")
        self._body_consumed = True
        raw = self.rfile.read(n) if n else b""
        if len(raw) != n:
            raise ApiError(400, "bad_json", "Body shorter than Content-Length")
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            raise ApiError(400, "bad_json", "Body must be UTF-8 JSON") from None
        if not isinstance(obj, dict):
            raise ApiError(400, "bad_json", "Body must be a JSON object")
        return obj

    # ---- routing --------------------------------------------------------
    def _handle(self, method):
        self._check_host()
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        m = ROUTE_ID_RE.fullmatch(path)
        if path in STATIC_FILES:
            allowed, fn = ("GET",), lambda: self._static(path)
        elif path == "/api/v1/health":
            allowed, fn = ("GET",), self._health
        elif path == "/api/v1/graph":
            allowed, fn = ("GET",), lambda: self._json(200, {"graph": fixture.graph_payload()})
        elif path == "/api/v1/route":
            allowed, fn = ("POST",), self._route
        elif path == "/api/v1/routes":
            allowed, fn = ("GET", "POST"), self._routes
        elif m:
            allowed, fn = ("GET",), lambda: self._get_route(int(m.group(1)))
        else:
            raise ApiError(404, "not_found", "Not found")
        if method not in allowed:
            raise ApiError(
                405, "method_not_allowed", "Method not allowed", {"Allow": ", ".join(allowed)}
            )
        if method == "POST":
            self._check_origin()
        fn()

    # ---- endpoints ------------------------------------------------------
    def _static(self, path):
        name, ctype = STATIC_FILES[path]
        try:
            with open(os.path.join(STATIC_DIR, name), "rb") as f:
                data = f.read()
        except OSError:
            raise ApiError(404, "not_found", "Not found") from None
        self._send(200, data, ctype)

    def _health(self):
        self._json(
            200,
            {"status": "ok", "version": __version__, "schema_version": self.server.store.schema_version},
        )

    def _compute(self, body):
        try:
            return routing.compute_route(body["from"], body["to"])
        except routing.UnknownLandmark as e:
            raise ApiError(404, "unknown_landmark", f"Unknown landmark: {e.landmark_id}") from None

    def _route(self):
        body = self._read_body_object()
        validate_ids(body, ("from", "to"))
        self._json(200, self._compute(body))

    def _routes(self):
        if self.command == "GET":
            self._json(200, {"routes": self._db(self.server.store.list_routes)})
            return
        body = self._read_body_object()
        validate_ids(body, ("title", "from", "to"))
        title = validate_title(body["title"])
        result = self._compute(body)
        if not result["reachable"]:
            raise ApiError(422, "unreachable", result["message"])
        try:
            saved = self._db(lambda: self.server.store.save_route(title, result, fixture.GRAPH_ID))
        except TitleExists:
            raise ApiError(409, "title_exists", f'A route titled "{title}" already exists') from None
        self._json(201, {"route": saved})

    def _get_route(self, route_id):
        route = self._db(lambda: self.server.store.get_route(route_id))
        if route is None:
            raise ApiError(404, "not_found", "Route not found")
        self._json(200, {"route": route})

    @staticmethod
    def _db(fn):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "locked" in str(e) or "busy" in str(e):
                raise ApiError(503, "busy", "Database busy, try again") from None
            raise


class RouteServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # on Windows SO_REUSEADDR allows port sharing
    request_queue_size = 32


def create_server(data_dir, port):
    """Prepare the data dir, migrate the DB, bind 127.0.0.1:port.

    Returns (server, actual_port). The caller runs serve_forever() and later
    shutdown()/server_close(). Raises StoreError (data dir/DB) or OSError (bind).
    """
    store = Store(prepare_data_dir(data_dir)).open()
    server = RouteServer((HOST, port), Handler)
    server.store = store
    return server, server.server_address[1]


def _port(text):
    v = int(text)
    if not 0 <= v <= 65535:
        raise argparse.ArgumentTypeError("port must be 0..65535")
    return v


def main(argv=None):
    parser = argparse.ArgumentParser(prog="offline_routes", description="Offline route planner")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", type=_port, default=8080)
    args = parser.parse_args(argv)
    try:
        server, port = create_server(args.data_dir, args.port)
    except StoreError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: cannot listen on {HOST}:{args.port}: {e}", file=sys.stderr)
        return 1
    try:
        print(f"Serving on http://{HOST}:{port}/", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.store.close()
    return 0
