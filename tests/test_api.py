import http.client
import json
import tempfile
import threading
import unittest

from offline_routes.server import create_server

JSON = {"Content-Type": "application/json"}


class ServerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self.data_dir = self._tmp.name
        self.start()

    def start(self):
        self.server, self.port = create_server(self.data_dir, 0)
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        self.thread.start()
        self._running = True

    def stop(self):
        if self._running:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(5)
            self._running = False

    def tearDown(self):
        self.stop()

    def request(self, method, path, body=None, headers=None, host="default", raw_body=None, port=None):
        """Send a request; returns (status, headers, parsed-json-or-bytes).

        `headers` are sent verbatim (no automatic Content-Length) so tests can
        omit or falsify it. Host defaults to 127.0.0.1:<port>.
        """
        port = port or self.port
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            if host == "default":
                host = f"127.0.0.1:{port}"
            if host is not None:
                conn.putheader("Host", host)
            payload = raw_body
            if body is not None:
                payload = json.dumps(body).encode()
            hdrs = dict(headers or {})
            for k, v in hdrs.items():
                conn.putheader(k, v)
            conn.endheaders(payload)
            resp = conn.getresponse()
            data = resp.read()
            ctype = resp.getheader("Content-Type") or ""
            parsed = json.loads(data) if ctype.startswith("application/json") else data
            return resp.status, resp, parsed
        finally:
            conn.close()

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body, extra=None, **kw):
        payload = json.dumps(body).encode()
        h = {"Content-Type": "application/json", "Content-Length": str(len(payload))}
        h.update(extra or {})
        return self.request("POST", path, raw_body=payload, headers=h, **kw)

    def assertError(self, result, status, code):
        s, resp, body = result
        self.assertEqual(s, status, body)
        self.assertEqual(set(body), {"error"})
        self.assertEqual(body["error"]["code"], code)
        self.assertIsInstance(body["error"]["message"], str)
        self.assertNotIn("Traceback", json.dumps(body))
        self.assertTrue(resp.getheader("Content-Type").startswith("application/json; charset=utf-8"))
        self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))


class ReadEndpointTests(ServerCase):
    def test_health(self):
        s, resp, body = self.get("/api/v1/health")
        self.assertEqual(s, 200)
        self.assertEqual(body, {"status": "ok", "version": "0.1.0", "schema_version": 1})
        self.assertEqual(resp.getheader("Content-Type"), "application/json; charset=utf-8")

    def test_graph(self):
        s, _, body = self.get("/api/v1/graph")
        self.assertEqual(s, 200)
        g = body["graph"]
        self.assertEqual(g["id"], "fixture-v1")
        self.assertEqual(
            g["nodes"][0], {"id": "depot", "name": "Depot", "x": 60, "y": 190}
        )
        self.assertEqual(
            [e["id"] for e in g["edges"]],
            ["depot-library", "library-observatory", "depot-observatory"],
        )

    def test_security_headers_everywhere(self):
        for path in ("/api/v1/health", "/nope"):
            _, resp, _ = self.get(path)
            self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
            self.assertEqual(resp.getheader("Cache-Control"), "no-store")
            self.assertIn("default-src 'self'", resp.getheader("Content-Security-Policy"))
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))

    def test_unknown_path_and_methods(self):
        self.assertError(self.get("/api/v1/nothing"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/abc"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/-1"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/1.5"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/99999"), 404, "not_found")
        r = self.request("OPTIONS", "/api/v1/routes")
        self.assertError(r, 405, "method_not_allowed")
        self.assertEqual(r[1].getheader("Allow"), "GET, POST")
        r = self.request("DELETE", "/api/v1/health")
        self.assertError(r, 405, "method_not_allowed")
        self.assertEqual(r[1].getheader("Allow"), "GET")
        self.assertError(self.get("/api/v1/route"), 405, "method_not_allowed")
        self.assertError(self.post("/api/v1/health", {}), 405, "method_not_allowed")
        self.assertError(self.post("/app.js", {}), 405, "method_not_allowed")


class StaticTests(ServerCase):
    EXPECT = {
        "/": "text/html; charset=utf-8",
        "/app.css": "text/css; charset=utf-8",
        "/app.js": "text/javascript; charset=utf-8",
    }

    def test_allowlist_serves_files(self):
        for path, ctype in self.EXPECT.items():
            s, resp, body = self.get(path)
            self.assertEqual(s, 200, path)
            self.assertEqual(resp.getheader("Content-Type"), ctype)
            self.assertIsInstance(body, bytes)
            self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
            self.assertIn("script-src 'self'", resp.getheader("Content-Security-Policy"))

    def test_index_has_required_labels(self):
        _, _, body = self.get("/")
        html = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        for needle in ("Calculate route", 'for="from"', 'for="to"', "Route title", "Save route"):
            self.assertIn(needle, html)

    def test_not_allowlisted_and_traversal(self):
        paths = [
            "/index.html",
            "/static/app.js",
            "/static/",
            "/server.py",
            "/../server.py",
            "/../../offline_routes/server.py",
            "/%2e%2e/server.py",
            "/%2e%2e/",
            "/..%2fserver.py",
            "/%2e%2e%2fstore.py",
            "/app.js/",
            "/app.js/../server.py",
            "/APP.JS",
            "/..\\server.py",
            "/routes.sqlite3",
            "/__init__.py",
        ]
        for p in paths:
            s, resp, body = self.get(p)
            self.assertEqual(s, 404, p)
            self.assertIsInstance(body, dict, p)
            self.assertEqual(body["error"]["code"], "not_found", p)

    def test_query_string_does_not_change_allowlist(self):
        s, _, _ = self.get("/app.js?../../server.py")
        self.assertIn(s, (200, 404))
        s, _, body = self.get("/server.py?/app.js")
        self.assertEqual(s, 404)


class RouteCalcTests(ServerCase):
    def test_reachable(self):
        s, _, body = self.post("/api/v1/route", {"from": "depot", "to": "observatory"})
        self.assertEqual(s, 200)
        self.assertEqual(body["distance_m"], 120)
        self.assertEqual(body["path"], ["depot", "library", "observatory"])
        self.assertEqual(body["steps"][-1], "Arrive at Observatory: 120 m total")

    def test_unreachable(self):
        s, _, body = self.post("/api/v1/route", {"from": "depot", "to": "island"})
        self.assertEqual(s, 200)
        self.assertFalse(body["reachable"])
        self.assertIsNone(body["distance_m"])
        self.assertEqual(body["message"], "No route from Depot to Island")

    def test_same_node(self):
        s, _, body = self.post("/api/v1/route", {"from": "library", "to": "library"})
        self.assertEqual((s, body["distance_m"], body["path"]), (200, 0, ["library"]))
        self.assertEqual(body["steps"], ["Already at Library"])

    def test_unknown_landmark(self):
        self.assertError(self.post("/api/v1/route", {"from": "depot", "to": "mars"}), 404, "unknown_landmark")

    def test_validation(self):
        bad = [
            {},
            {"from": "depot"},
            {"to": "depot"},
            {"from": "depot", "to": "library", "extra": 1},
            {"from": 1, "to": "library"},
            {"from": "depot", "to": None},
            {"from": "depot", "to": ["library"]},
            {"from": "", "to": "library"},
            {"from": "d" * 65, "to": "library"},
        ]
        for b in bad:
            self.assertError(self.post("/api/v1/route", b), 400, "validation")
        # 64 chars is valid syntactically, so it reaches the landmark lookup.
        self.assertError(
            self.post("/api/v1/route", {"from": "d" * 64, "to": "library"}), 404, "unknown_landmark"
        )


class RequestSafetyTests(ServerCase):
    BODY = {"from": "depot", "to": "library"}

    def test_content_type_415(self):
        payload = json.dumps(self.BODY).encode()
        for ct in ("text/plain", "application/x-www-form-urlencoded", "application/jsonx", None):
            h = {"Content-Length": str(len(payload))}
            if ct:
                h["Content-Type"] = ct
            self.assertError(
                self.request("POST", "/api/v1/route", raw_body=payload, headers=h),
                415,
                "unsupported_media_type",
            )

    def test_content_type_params_and_case_ok(self):
        payload = json.dumps(self.BODY).encode()
        h = {"Content-Type": "Application/JSON; charset=utf-8", "Content-Length": str(len(payload))}
        s, _, _ = self.request("POST", "/api/v1/route", raw_body=payload, headers=h)
        self.assertEqual(s, 200)

    def test_length_required_411(self):
        self.assertError(
            self.request("POST", "/api/v1/route", headers=JSON), 411, "length_required"
        )

    def test_too_large_413(self):
        # Header claims too much; server must refuse without reading it.
        self.assertError(
            self.request(
                "POST", "/api/v1/route", headers={**JSON, "Content-Length": "4097"}
            ),
            413,
            "too_large",
        )
        self.assertError(
            self.request(
                "POST", "/api/v1/route", headers={**JSON, "Content-Length": "99999999999"}
            ),
            413,
            "too_large",
        )

    def test_exactly_max_body_ok(self):
        base = json.dumps(self.BODY).encode()
        payload = base + b" " * (4096 - len(base))
        self.assertEqual(len(payload), 4096)
        h = {**JSON, "Content-Length": "4096"}
        s, _, _ = self.request("POST", "/api/v1/route", raw_body=payload, headers=h)
        self.assertEqual(s, 200)

    def test_bad_content_length(self):
        for v in ("abc", "-1", "1e3", ""):
            self.assertError(
                self.request("POST", "/api/v1/route", headers={**JSON, "Content-Length": v}),
                400,
                "bad_request",
            )

    def test_bad_json(self):
        cases = [b"not json", b"", b"[1,2]", b'"s"', b"null", b"{", b"\xff\xfe{}", b"[" * 3000]
        for raw in cases:
            h = {**JSON, "Content-Length": str(len(raw))}
            self.assertError(
                self.request("POST", "/api/v1/route", raw_body=raw, headers=h), 400, "bad_json"
            )

    def test_body_shorter_than_length(self):
        h = {**JSON, "Content-Length": "50"}
        # Server waits for the missing bytes; close from our side by sending fewer
        # and shutting down the write half.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest("POST", "/api/v1/route", skip_host=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            for k, v in h.items():
                conn.putheader(k, v)
            conn.endheaders(b'{"from"')
            conn.sock.shutdown(1)
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
            self.assertEqual(json.loads(resp.read())["error"]["code"], "bad_json")
        finally:
            conn.close()

    def test_host_forbidden(self):
        for host in ("evil.com", f"evil.com:{self.port}", "127.0.0.1", "127.0.0.1:1", "localhost", None):
            self.assertError(
                self.post("/api/v1/route", self.BODY, host=host), 403, "forbidden_host"
            )
        self.assertError(self.get("/api/v1/health", host="evil.com"), 403, "forbidden_host")

    def test_host_allowed_forms(self):
        for host in (f"127.0.0.1:{self.port}", f"localhost:{self.port}", f"LOCALHOST:{self.port}"):
            s, _, _ = self.post("/api/v1/route", self.BODY, host=host)
            self.assertEqual(s, 200, host)

    def test_origin(self):
        for origin in (
            "http://evil.com",
            "null",
            f"https://127.0.0.1:{self.port}",
            f"http://127.0.0.1:{self.port + 1}",
            "http://127.0.0.1",
            "",
        ):
            self.assertError(
                self.post("/api/v1/route", self.BODY, extra={"Origin": origin}),
                403,
                "forbidden_origin",
            )
        for origin in (f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"):
            s, resp, _ = self.post("/api/v1/route", self.BODY, extra={"Origin": origin})
            self.assertEqual(s, 200)
            self.assertIsNone(resp.getheader("Access-Control-Allow-Origin"))

    def test_forbidden_origin_does_not_save(self):
        self.post(
            "/api/v1/routes",
            {"title": "Sneaky", "from": "depot", "to": "library"},
            extra={"Origin": "http://evil.com"},
        )
        self.assertEqual(self.get("/api/v1/routes")[2], {"routes": []})


class SavedRouteTests(ServerCase):
    def save(self, title="Morning run", frm="depot", to="observatory", **kw):
        return self.post("/api/v1/routes", {"title": title, "from": frm, "to": to}, **kw)

    def test_save_list_get(self):
        s, _, body = self.save()
        self.assertEqual(s, 201)
        r = body["route"]
        self.assertEqual(r["id"], 1)
        self.assertEqual(r["title"], "Morning run")
        self.assertEqual(r["from"], "depot")
        self.assertEqual(r["distance_m"], 120)
        self.assertEqual(r["path"], ["depot", "library", "observatory"])
        self.assertEqual(len(r["steps"]), 4)
        self.assertEqual(r["graph_id"], "fixture-v1")
        self.assertRegex(r["created_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.save("Second", "library", "library")
        s, _, lst = self.get("/api/v1/routes")
        self.assertEqual(s, 200)
        self.assertEqual([x["id"] for x in lst["routes"]], [2, 1])
        self.assertEqual(
            set(lst["routes"][0]),
            {"id", "title", "from", "to", "distance_m", "created_at"},
        )
        self.assertEqual(lst["routes"][0]["distance_m"], 0)
        s, _, got = self.get("/api/v1/routes/1")
        self.assertEqual((s, got), (200, {"route": r}))

    def test_empty_list(self):
        self.assertEqual(self.get("/api/v1/routes")[2], {"routes": []})

    def test_title_trimmed(self):
        s, _, body = self.save("   padded  ")
        self.assertEqual(body["route"]["title"], "padded")
        self.assertError(self.save("PADDED"), 409, "title_exists")

    def test_title_validation(self):
        for t in ("", "   ", "a" * 81, "tab\there", "new\nline", "nul\x00", "bell\x07", 5, None, ["x"], "\ud800"):
            self.assertError(self.save(t), 400, "validation")
        s, _, _ = self.save("é" * 80)
        self.assertEqual(s, 201)
        s, _, _ = self.save("b" * 80)
        self.assertEqual(s, 201)
        self.assertEqual(len(self.get("/api/v1/routes")[2]["routes"]), 2)

    def test_unicode_title_roundtrip(self):
        s, _, body = self.save("Café ☕ 路线")
        self.assertEqual(s, 201)
        self.assertEqual(self.get("/api/v1/routes/1")[2]["route"]["title"], "Café ☕ 路线")

    def test_duplicate_409_case_insensitive_and_no_data_loss(self):
        self.assertEqual(self.save("Morning run")[0], 201)
        for t in ("Morning run", "morning RUN", "MORNING RUN", "  Morning run "):
            r = self.save(t, "depot", "library")
            self.assertError(r, 409, "title_exists")
            self.assertIn(t.strip(), r[2]["error"]["message"])
        routes = self.get("/api/v1/routes")[2]["routes"]
        self.assertEqual(len(routes), 1)
        self.assertEqual(routes[0]["to"], "observatory")

    def test_unreachable_422_and_unknown_404(self):
        self.assertError(self.save("Isle", "depot", "island"), 422, "unreachable")
        self.assertError(self.save("Nowhere", "depot", "mars"), 404, "unknown_landmark")
        self.assertEqual(self.get("/api/v1/routes")[2], {"routes": []})
        # Failed attempts must not consume the title.
        self.assertEqual(self.save("Isle", "depot", "library")[0], 201)

    def test_save_validation(self):
        bad = [
            {"from": "depot", "to": "library"},
            {"title": "x", "to": "library"},
            {"title": "x", "from": "depot", "to": "library", "path": ["depot"]},
            {"title": "x", "from": 1, "to": "library"},
        ]
        for b in bad:
            self.assertError(self.post("/api/v1/routes", b), 400, "validation")

    def test_server_ignores_client_path(self):
        # Extra keys are rejected, so a forged path/distance can never be stored.
        r = self.post(
            "/api/v1/routes",
            {"title": "Forged", "from": "depot", "to": "observatory", "distance_m": 1, "path": []},
        )
        self.assertError(r, 400, "validation")

    def test_get_route_not_found(self):
        self.assertError(self.get("/api/v1/routes/1"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/0"), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/" + "9" * 19), 404, "not_found")
        self.assertError(self.get("/api/v1/routes/%31"), 404, "not_found")

    def test_concurrent_same_title_exactly_one_201(self):
        n = 12
        titles = ["Race", "race", "RACE"]
        barrier = threading.Barrier(n)
        results = []
        lock = threading.Lock()

        def worker(i):
            barrier.wait()
            r = self.save(titles[i % 3])
            with lock:
                results.append(r[0])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(len(results), n)
        self.assertEqual(results.count(201), 1, results)
        self.assertEqual(results.count(409), n - 1, results)
        self.assertEqual(len(self.get("/api/v1/routes")[2]["routes"]), 1)

    def test_concurrent_distinct_titles_all_saved(self):
        n = 8
        results = []
        lock = threading.Lock()

        def worker(i):
            r = self.save(f"Route {i}")
            with lock:
                results.append(r[0])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(results, [201] * n)
        ids = sorted(x["id"] for x in self.get("/api/v1/routes")[2]["routes"])
        self.assertEqual(ids, list(range(1, n + 1)))


class PersistenceTests(ServerCase):
    def test_restart_keeps_routes(self):
        s, _, body = self.post(
            "/api/v1/routes", {"title": "Persist", "from": "depot", "to": "observatory"}
        )
        self.assertEqual(s, 201)
        saved = body["route"]
        self.stop()
        self.start()  # same data dir, new port
        s, _, lst = self.get("/api/v1/routes")
        self.assertEqual([r["title"] for r in lst["routes"]], ["Persist"])
        self.assertEqual(self.get("/api/v1/routes/1")[2], {"route": saved})
        self.assertEqual(self.get("/api/v1/health")[2]["schema_version"], 1)
        # Uniqueness and id sequence survive the restart.
        r = self.post("/api/v1/routes", {"title": "persist", "from": "depot", "to": "library"})
        self.assertError(r, 409, "title_exists")
        s, _, b2 = self.post("/api/v1/routes", {"title": "Next", "from": "depot", "to": "library"})
        self.assertEqual(b2["route"]["id"], 2)

    def test_old_port_host_rejected_after_restart(self):
        old = self.port
        self.stop()
        self.start()
        if self.port != old:
            self.assertError(
                self.post("/api/v1/route", {"from": "depot", "to": "library"}, host=f"127.0.0.1:{old}"),
                403,
                "forbidden_host",
            )

    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
