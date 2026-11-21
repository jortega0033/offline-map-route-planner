# Offline Map and Route Planner: PRD and technical spec

Status legend: **[Baseline]** implemented in M1 (see [baseline verification](../README.md#baseline-verification)), **[Future]** specified only, not built.

## 1. Intended user and workflow

A traveler or dispatcher working alone on one computer needs routing when live map services are unavailable. They open a local page, pick a start (From) and end (To) landmark, calculate the exact shortest route, read ordered steps, name and save the route, and reopen it later, including after restarting the program.

M1 workflow: start server, open `http://127.0.0.1:<port>/`, choose From and To, press Calculate route, read steps and distance, type a Route title, press Save route, later press the saved route's button to reopen.

## 2. Scope

In scope [Baseline]: a built-in, original fictional graph; Dijkstra shortest path; map drawing; textual steps; SQLite persistence of named routes; loopback-only server.

Out of scope: external map services, tiles, real addresses or geolocation, user sign-in, remote sync, payments, deployment, model integrations, real user data, external media.

## 3. Milestones

| Milestone | Content | Status |
|---|---|---|
| M1 | Fixture graph, route calculation, steps, save and reopen | [Baseline] |
| OR-1 | Bounded graph-pack import and revisions | [Future] ticket P1 |
| OR-2 | Viewport projection, pan/zoom, culling, 100k seeded fixture | [Future] ticket P2 |
| OR-3 | Landmark and licensed-address index | [Future] ticket P3 |
| OR-4 | One-way and cost-aware routing | [Future] ticket P4 |
| OR-5 | Revision-pinned routes, reproducible verification | [Future] ticket P5 |

## 4. Epic: Offline routing beyond the fixture graph

Exactly one epic covers all future work. Epic acceptance: import, route, save, re-import and reopen the first route unchanged; 100k-segment graph pans without offscreen elements; directed routing agrees with a reference Dijkstra including no-path cases; saved routes verify against their pinned revision and dataset hash.

### User stories, dependencies and acceptance (future issues)

**P1 / OR-1 Graph-pack import (depends on: none).** As a dispatcher I load a bounded pack of cleared synthetic data so I can route on my own graph.
- Limits: 2 MiB body, 5,000 nodes, 20,000 edges, ids <= 64 chars, integer meters 1..1,000,000. Oversized body returns 413; too many nodes or edges returns 422.
- Migration v2 seeds the built-in `fixture-v1` graph as revision 1 and adds `routes.revision_id`, so existing saved routes stay bound to revision 1.
- Import is one transaction; a single invalid edge (unknown endpoint, duplicate id, self loop, non-positive meters) rejects the whole pack, reports up to 20 JSON-path errors, and leaves revisions unchanged.
- A pack with 100 valid edges plus one edge to `ghost` returns 422 and the revision count is unchanged; a route saved on revision 1 reopens identically after revision 2 is imported.

**P2 / OR-2 Viewport and culling (depends on: P1).** As a traveler I pan and zoom a large graph smoothly.
- The generated graph is created on demand by the explicit Load large fixture action and is exempt from the P1 import limits (it is never posted as a pack).
- Seeded generator (seed 7) yields exactly 100,000 segments with identical first feature id and total length across runs.
- `GET /api/v1/graph/features` with a bbox returns <= 2,000 features, none fully outside the bbox; the client draws only returned features and creates no elements for offscreen ones.
- Zoom clamped 0.25x..32x, Reset view exact, keyboard operable, no body overflow at 800x600.

**P3 / OR-3 Search index (depends on: P1).** As a user I find places by typing part of a name.
- Normalisation: NFKD, strip marks, casefold. Ranking: exact, prefix, word prefix, substring; ties by shorter name, casefolded name, id. Duplicate names are disambiguated by locality.
- `cafe` returns `Café Central` first; identical queries return byte-identical JSON; q length 2..64.
- Address sample only with license manifest and sha256 check; mismatch loads nothing.

**P4 / OR-4 One-way and cost-aware routing (depends on: P1).** As a dispatcher I respect one-way edges and choose shortest or fastest.
- Tie-break order: total cost, fewer edges, lexicographic node-id sequence.
- 200 generated directed graphs (30 nodes) match a reference Dijkstra on total cost for all ordered pairs, including unreachable pairs reported as `reachable:false`.
- One-way A to B has a route A to B and none B to A when no alternative path exists; instructions name edge, distance and one-way marker.

**P5 / OR-5 Pinned routes and verification (depends on: P1, P4).** As a user I trust that a saved route can be reproduced.
- Saved route additionally stores planner version and dataset sha256 (revision binding comes from P1).
- `python -m offline_routes verify --data-dir <path>` exits 0 (all match), 1 (mismatch or missing revision), 2 (usage or storage error), with deterministic output.
- Reopen shows the pinned result; Recalculate on current revision is separate and non-destructive.
- Future preflight for importing permitted real-world extracts (documentation only): see section 14.

## 5. System stack [Baseline]

- Python 3.12 standard library only: `http.server.ThreadingHTTPServer`, `sqlite3`, `heapq`, `unittest`.
- Static HTML/CSS/native JS in `offline_routes/static/`, no build step, no external URLs.
- Binds 127.0.0.1 only. Entry point `python -m offline_routes --data-dir <path> --port <port>`.
- Server threads are daemon threads with a 10 s socket timeout; Ctrl+C shuts the server down. Each request opens and closes its own SQLite connection.

## 6. API contract [Baseline]

Errors: `{"error":{"code","message"}}`. Bodies are `application/json; charset=utf-8`. POST requires `Content-Type: application/json` and a `Content-Length` of at most 4096 bytes.

Request and response shapes:
- `POST /api/v1/route` body `{"from":"depot","to":"observatory"}` returns `{"reachable":true,"from","to","distance_m":120,"path":["depot","library","observatory"],"steps":[...]}`; unreachable returns `{"reachable":false,"distance_m":null,"path":[],"steps":[],"message":"No route from Depot to Island"}`.
- `POST /api/v1/routes` body `{"title","from","to"}`; the server recomputes the route and returns `{"route":{"id","title","from","to","distance_m","path","steps","graph_id","created_at"}}`.
- `GET /api/v1/routes` returns `{"routes":[{"id","title","from","to","distance_m","created_at"}]}` ordered by id descending.
- `GET /api/v1/graph` returns `{"graph":{"id":"fixture-v1","width":400,"height":260,"nodes":[{"id","name","x","y"}],"edges":[{"id","from","to","meters"}]}}`.

| Method and path | Success | Errors |
|---|---|---|
| GET / | 200 HTML | |
| GET /api/v1/health | 200 `{"status":"ok","version":"0.1.0","schema_version":1}` | |
| GET /api/v1/graph | 200 nodes and edges | |
| POST /api/v1/route | 200 route or unreachable result | 400 validation, 404 unknown_landmark |
| POST /api/v1/routes | 201 saved route | 400, 404, 409 title_exists, 422 unreachable |
| GET /api/v1/routes | 200 list, newest first | |
| GET /api/v1/routes/{id} | 200 route | 404 not_found |

Common: 403 `forbidden_host` (Host is checked on every request) and `forbidden_origin` (checked on POST); 400 `bad_json`, 400 `bad_request` (malformed request line, headers or Content-Length); 405 `method_not_allowed` with `Allow`; 411 `length_required`; 413 `too_large` (declared length > 4096); 415 `unsupported_media_type`; 501 `method_not_implemented`; 503 `busy` (database locked); 500 `internal` (no traceback). Process exit codes: 2 for data-directory errors, 1 if the port cannot be bound.

## 7. Schema [Baseline]

`schema_migrations(version)` plus `routes(id, title CHECK length 1..80, title_key UNIQUE, from_id, to_id, distance_m CHECK >= 0, path_json, steps_json, graph_id, created_at)`. Migrations are an ordered list applied in a transaction; reopening is a no-op. DB file: `<data-dir>/routes.sqlite3`, WAL, busy timeout 5 s.

## 8. Algorithm contract [Baseline]

Dijkstra with a binary heap, integer meters, undirected edges, tie-break (distance, node id). Same From and To returns 0 m and `[id]`. Unreachable returns `reachable:false` with empty path and steps. Steps format: `Start at X`, `Go from A to B (n m)`, `Arrive at Y: <total> m total`. Same-node routes use `Already at X`.

## 9. UI contract [Baseline]

Labeled From and To selects, Calculate route button, canvas map (`role="img"` with a text label) with a visible Connections list as text equivalent, ordered steps list, status line with `role="status"`, Route title input, Save route button, saved-route buttons whose visible name is exactly the title. Any change, error, or unreachable result clears the preview and steps and disables Save. Text is inserted with `textContent` only.

## 10. Deterministic fixtures

Nodes: Depot, Library, Observatory, Island. Edges: Depot-Library 70 m, Library-Observatory 50 m, Depot-Observatory 165 m. Island has no edges.

| From | To | Expected |
|---|---|---|
| Depot | Observatory | Depot, Library, Observatory; 120 m |
| Observatory | Depot | Observatory, Library, Depot; 120 m |
| Depot | Library | 70 m |
| Library | Observatory | 50 m |
| Depot | Island | unreachable, preview cleared |
| Library | Library | 0 m, `Already at Library` |

## 11. Responsiveness, accessibility, errors, concurrency

- Two columns at >= 720 px, one column below; no body overflow at 800x600 or 360 px width.
- Real labels, `:focus-visible` outline, system fonts, contrast >= 4.5:1, route and endpoints distinguished by shape and text, not color alone, reduced-motion respected.
- Errors are recoverable: network failure shows "Server unreachable. Check that it is running, then try again."; the title text is kept on 409 and network failure. Retrying a Save with the same title after a 409 changes nothing in storage.
- Concurrency: title uniqueness is enforced by a UNIQUE constraint, so of N concurrent saves with the same title exactly one succeeds.
- Restart: saved routes persist in the data directory across restarts.

## 12. Security and validation [Baseline]

Loopback bind; Host checked on every request, Origin on POST; no CORS headers; JSON object bodies only, <= 4096 bytes; title NFC-normalised, trimmed, 1..80 chars without control or format characters; id fields <= 64 chars; static files from a fixed allowlist (`/`, `/app.css`, `/app.js`); CSP and `nosniff` headers; parameterised SQL; no secrets, no user data.

## 12a. Versioning

Application version `0.1.0` (reported by health). API paths are prefixed `/api/v1/`; breaking changes need `/api/v2/`. Schema versions are recorded in `schema_migrations` and applied in order inside one transaction; a database with a newer schema than the program is refused (exit 2). Graph revisions arrive with P1.

## 13. Acceptance matrix (M1)

| ID | Check | Measure |
|---|---|---|
| A1 | Depot to Observatory | path `depot,library,observatory`, 120 m |
| A2 | Depot to Island | `reachable:false`, steps empty, UI preview cleared |
| A3 | Save then restart then reopen | same title, 120 m, 4 steps |
| A4 | Duplicate title (any case) | 409, text retained |
| A5 | 8 concurrent saves, same title | exactly one 201 |
| A6 | Foreign Host or Origin on POST | 403, nothing stored |
| A7 | Body of 4097 bytes | 413 |
| A8 | `/../offline_routes/server.py` | 404 |
| A9 | Bad `--data-dir` (empty, a file) | exit 2 |
| A10 | 800x600 layout | no horizontal body scroll |
| A11 | Keyboard-only flow | all controls reachable, focus visible |
| A12 | Title `<img src=x onerror=1>` | shown as literal text |

## 14. Sample demo and test plan

Demo: launch, Depot to Observatory, Calculate route, 120 m with four steps, title "Morning run", Save route, restart with the same `--data-dir`, press "Morning run", the same steps appear; then Depot to Island shows "No route from Depot to Island" and no stale steps.

Automated: `python -m unittest discover -s tests -t .` runs routing, API, storage and security tests on disposable temp directories and port 0. Manual: browser smoke steps in the README, keyboard pass, 800x600 resize check.

Future preflight for permitted extracts (documentation only, not built): (1) written license permits local redistribution; (2) size under the pack limits or split; (3) sha256 recorded in a manifest; (4) dry run on synthetic-only copy reports zero rejected edges; (5) no personal data or precise real home addresses in the extract; (6) attribution text stored with the revision. Any required external tool must be offline-plannable and approved before staging.

## 15. Open choices

- Combobox versus select once graphs exceed a few hundred landmarks (OR-3).
- Whether fastest profile needs per-edge speed or an explicit seconds field (OR-4).
- Storing full path steps per revision versus recomputing on reopen (OR-5).
- Whether pan/zoom features come from SQL range queries or an in-memory grid (OR-2).
