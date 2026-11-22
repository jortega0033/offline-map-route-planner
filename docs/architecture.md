# Architecture notes and PRD drift

This file describes the code as it is at commit `5eb9f1f` (M1 baseline), traces one real workflow through it, and records where [PRD.md](PRD.md) and the code differ. It was written during backlog preparation on 2026-11-22. Line numbers refer to that commit.

Status words used below:

- **Implemented**: present in the code and observed working during preparation (see [section 8](#8-what-was-run-during-preparation)).
- **Planned**: specified in the PRD or in an issue, no code yet.
- **Needs verification**: claimed somewhere, or read in the code, but not observed during preparation.

## 1. Shape of the system

One Python process, standard library only, no build step. It serves a JSON API and three static files on `127.0.0.1` and keeps saved routes in one SQLite file. The page is native HTML, CSS and JavaScript.

| Module | Job | Must not |
|---|---|---|
| `offline_routes/__main__.py` | Calls `server.main` and exits with its return code. | Hold logic. |
| `offline_routes/server.py` | Command line (`main`, line 301), `create_server` (282), the HTTP handler: request guards, static allowlist, security headers, JSON envelope, body validation (`validate_ids` 44, `validate_title` 54), mapping of errors to status codes. | Run SQL or contain routing logic. |
| `offline_routes/routing.py` | `shortest_path` (25): Dijkstra with a binary heap over integer meters. `compute_route` (70): builds the response body and the step texts. | Touch HTTP objects or the database. |
| `offline_routes/fixture.py` | The built-in graph `fixture-v1` as module constants (`NODES` 8, `EDGES` 16) and `graph_payload` (25). | Change: saved routes refer to it by id. |
| `offline_routes/store.py` | The only module that imports `sqlite3` for application data: `prepare_data_dir` (37), ordered migrations (`MIGRATIONS` 11, `apply_migrations` 65), `Store` (116) with `save_route`, `list_routes`, `get_route`. | Touch HTTP objects. |
| `offline_routes/static/` | `index.html`, `app.css`, `app.js`. One page, one script, no framework. Talks to the server through `/api/v1` only and stores nothing in the browser. | Load anything from another host, or put data into the page other than through `textContent`. |
| `tests/` | `unittest`. `test_routing.py` (9 tests) calls the algorithm directly. `test_store.py` (14) drives `Store`, the migrations and `main`. `test_api.py` (40) starts a real server on port 0 per test and uses `http.client`. | Use a fixed port, the network, or a directory outside `tempfile`. |

`server.py` imports `sqlite3` only to recognise a locked database in `_db` (266 to 273).

## 2. Traced workflow: calculate, save, restart, reopen

The M1 demo from PRD section 14, followed through the code. Every step was also observed over HTTP and in a browser (section 8).

1. **Start.** `python -m offline_routes --data-dir D --port P` reaches `server.main` (`server.py:301`). `create_server` (282) calls `prepare_data_dir` (`store.py:37`), which creates the directory or raises `StoreError`, then `Store.open` (`store.py:123`), which sets WAL mode and runs `apply_migrations` (`store.py:65`) inside one `BEGIN IMMEDIATE` transaction. Then it binds `RouteServer` to `127.0.0.1:P` (`server.py:289`). `main` prints `Serving on http://127.0.0.1:<port>/`. A `StoreError` exits with 2 (`server.py:308`), a failed bind with 1 (`server.py:311`).
2. **Page load.** `GET /` passes `_check_host` (`server.py:138`) and is answered from the allowlist `STATIC_FILES` (`server.py:20`, `_static` 218). The script calls `loadGraph` (`app.js:95`), which fetches `GET /api/v1/graph`. The server answers with `fixture.graph_payload()` (`server.py:200`). The script fills both selects (`fillSelect`, `app.js:86`), writes the Connections list, draws the canvas (`draw`, `app.js:140`), then fetches `GET /api/v1/routes` (`loadSaved`, `app.js:339`).
3. **Calculate.** Submitting the form runs `calculate` (`app.js:245`), which first clears any preview and then posts `{"from","to"}` to `/api/v1/route`. On the server `_handle` (`server.py:191`) checks Host, the method and, for POST, Origin (`_check_origin` 143). `_route` (239) reads the body with `_read_body_object` (164: media type, `Content-Length` present and at most `MAX_BODY` = 4096, UTF-8 JSON object), checks the keys and id lengths with `validate_ids` (44) and calls `routing.compute_route` (`routing.py:70`). That calls `shortest_path` (`routing.py:25`) and builds `steps`. An unknown id raises `UnknownLandmark`, mapped to 404 `unknown_landmark` (`server.py:236`). No path is a normal 200 answer with `"reachable": false`.
4. **Preview.** `showPreview` (`app.js:45`) writes each step with `textContent`, shows the total, enables Save and redraws the canvas with the path highlighted.
5. **Save.** `save` (`app.js:283`) posts `{"title","from","to"}` to `/api/v1/routes`. `_routes` (`server.py:244`) validates the title (`validate_title` 54: NFC, trimmed, 1 to 80 characters, no control or format characters), **recomputes the route on the server** (251), answers 422 `unreachable` if there is none, and calls `Store.save_route` (`store.py:136`) with `fixture.GRAPH_ID` (`server.py:255`). The insert stores `title_key = title.casefold()`; the `UNIQUE` constraint on it turns a duplicate into `TitleExists` (`store.py:158`), mapped to 409 `title_exists` (`server.py:256`).
6. **Restart.** Nothing is held in memory. A new process on the same data directory runs the migrations again as a no-op and serves the same rows.
7. **Reopen.** A saved-route button calls `reopen` (`app.js:354`), which fetches `GET /api/v1/routes/{id}` (`server.py:260`, `store.py:192`). The page sets both selects to the stored ids and shows the **stored** `path` and `steps`. It does not recalculate.

## 3. Data ownership

- The graph is owned by `fixture.py`. `routing.py` reads it through default arguments (`routing.py:25`) and directly (`_edge_meters` 66, `compute_route` 72). `server.py` reads it at lines 200 and 255. There is no graph table, no revision and no import.
- Saved routes are owned by SQLite: table `routes` (`store.py:15` to 23) in `<data-dir>/routes.sqlite3`. A row keeps the title, the two ids, the distance, the path and the step texts as JSON, the text `graph_id` and a UTC timestamp.
- The client owns nothing durable. It never sends a path or a distance: a body with any extra key is refused with 400 (`validate_ids`, `server.py:46`; test `test_server_ignores_client_path`).

## 4. Rules the code keeps

A change must keep these, or change them on purpose with a test and a PRD edit in the same pull request.

1. **Loopback only.** The server binds `127.0.0.1` (`server.py:15`, 289). `Host` must be `127.0.0.1:<port>` or `localhost:<port>` on every request (134 to 141). `Origin`, when present on a POST, must match (143 to 149). No CORS header is ever sent.
2. **Bounded input.** A POST needs `Content-Type: application/json` and a `Content-Length` of at most 4096; the body is not read when the declared length is larger (`server.py:176`). Titles are 1 to 80 characters, ids 1 to 64.
3. **Fixed static allowlist.** Request input is never joined into a file path (`server.py:20`, 195).
4. **Every response** carries `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and the CSP (`server.py:80` to 82). Errors use `{"error":{"code","message"}}` and never contain a traceback (`_dispatch`, 117 to 131).
5. **The server computes, the client displays.** Route results come from `routing.py` only.
6. **Titles are unique without regard to case**, enforced by the database, not by a check before the insert (`store.py:18`). Of several concurrent saves with one title exactly one succeeds.
7. **Migrations only go forward.** `MIGRATIONS` is an ordered list of SQL statement lists, applied in one transaction; a failure rolls everything back (`store.py:92`). A database with a version this program does not know is refused (`store.py:78` to 82) and the process exits with 2.
8. **One short-lived connection per store operation** (`store.py:53`), WAL, 5 s busy timeout, `foreign_keys=ON`. A locked database becomes 503 `busy` (`server.py:266`).
9. **Deterministic routing.** The heap orders by `(distance, node id)`; on equal distance the smaller predecessor id wins (`routing.py:51`). Parallel edges use the smaller length (`routing.py:20`). Edges are undirected.
10. **Text reaches the page through `textContent` only.** `app.js` contains no `innerHTML`.
11. **A stale preview is never left on screen.** Any selection change, new calculation, error or unreachable result clears steps, total and highlight and disables Save (`clearPreview`, `app.js:34`; `onSelectionChange` 238).
12. **Connections close after each response** (HTTP/1.0, `close_connection = True`, 10 s socket timeout: `server.py:69`, 70, 118). `allow_reuse_address = False` is deliberate: on Windows the option would let a second process share the port (`server.py:278`).

## 5. PRD capabilities and their status

| PRD item | Status | Evidence or tracking |
|---|---|---|
| M1: fixture graph, shortest path, steps (sections 8, 10) | Implemented | `fixture.py`, `routing.py`; tests; all six fixture rows of section 10 observed over HTTP except Depot to Library and Library to Observatory, which are covered by `test_direct_edge_not_shorter` and the step texts |
| M1: API table and error codes (section 6) | Implemented | `server.py:191` to 215; `tests/test_api.py` |
| M1: schema, migrations, WAL (section 7) | Implemented | `store.py`; restart observed |
| M1: duplicate title, concurrent saves (section 11) | Implemented | `test_concurrent_same_title_exactly_one_201` (12 threads, three spellings); 409 observed in the page |
| M1: security and validation (section 12) | Implemented | 403 for a foreign Host and a foreign Origin, 413 for 4097 bytes, 404 for a traversal path, all observed |
| M1: UI contract (section 9) | Implemented | Browser run in section 8 |
| M1: layout at 800x600 and 360 wide, keyboard order, focus outline (section 11, A10, A11) | Implemented | Browser run in section 8 |
| M1: contrast of at least 4.5:1, reduced motion, shape as well as colour (section 11) | Needs verification | Read in `app.css` and `app.js`; not measured |
| M1 on Python 3.12 and on Linux | Needs verification | README records a run on Ubuntu 24.04 WSL with Python 3.12.3; preparation ran Windows with Python 3.13.14 only |
| OR-1 graph packs and revisions (P1) | Planned | Issue #NEW-A (revisions, pinning, graph store) and issue #2 (import) |
| OR-2 viewport, pan and zoom, culling, 100k fixture (P2) | Planned | Issue #3 |
| OR-3 landmark and address search (P3) | Planned | Issue #4 |
| OR-4 one-way and cost-aware routing (P4) | Planned | Issue #5 |
| OR-5 verification of pinned routes (P5) | Planned | Issue #6; the pin columns themselves are in #NEW-A |
| Section 14 preflight for real-world extracts | Planned, documentation only | Issue #6 |
| Epic acceptance run and document reconciliation | Planned | Issue #NEW-B |

No planned endpoint exists yet: `/api/v1/graph-packs`, `/api/v1/search` and `/api/v1/graph/features` each answered 404 `not_found` during preparation.

## 6. Differences between the PRD and the code

| # | PRD or README says | Code or observation | Consequence |
|---|---|---|---|
| D1 | "Requires Python 3.12" (README), "Python 3.12 standard library only" (PRD section 5). | No version check anywhere. The README's own record and this preparation ran 3.13.14 on Windows. | Read it as "3.12 or newer". Tickets must not use anything newer than 3.12. |
| D2 | Saved routes "stay bound to revision 1" (PRD section 4, P1). | `routes.graph_id` is free text set from a constant. `reopen` (`app.js:354` to 376) sets the two selects from the stored ids and guards only against ids missing from the current selects. | Harmless with one graph. As soon as a second graph exists, a reopened route would be drawn on the wrong graph. Fixed by #NEW-A (pin columns, graph loaded per revision) and #6 (pinned view and Recalculate). |
| D3 | Tie-break "(distance, node id)" (PRD section 8); P4 asks for "total cost, fewer edges, lexicographic node-id sequence". | Today: heap order `(distance, node id)` plus smaller predecessor id on equal distance. The two rules agree on `test_tie_break_is_deterministic` and the built-in graph has no ties. | #5 replaces the rule. A route saved before #5 can only differ on a tie; the planner version stored with each route (from #NEW-A) makes that visible. |
| D4 | POST bodies are "at most 4096 bytes" for every route (PRD section 6); P1 needs 2 MiB for one route. | `MAX_BODY` is one module constant (`server.py:16`); `_drain_small_body` (151) assumes at most four digits; the socket timeout is 10 s. | #2 adds a per-route cap and must keep 4096 on every other route. |
| D5 | The unreachable answer is `{"reachable":false,"distance_m":null,"path":[],"steps":[],"message"}` (PRD section 6). | The code also returns `from` and `to` (`routing.py:75` to 83). | PRD example is incomplete; the code is the contract. |
| D6 | Future tickets are called P1 to P5 (PRD sections 3, 4). | The issues are #2 to #6 under the epic #1, plus #NEW-A and #NEW-B. | Mapping: P1 is #NEW-A and #2, P2 is #3, P3 is #4, P4 is #5, P5 is #6. |
| D7 | A5: "8 concurrent saves, same title". | The test uses 12 threads and three spellings of one title. | Stronger than the PRD row; no action. |
| D8 | The graph payload carries `width` and `height` (PRD section 6). | The page ignores them and uses its own constants `W = 400, H = 260` (`app.js:4`). | Any graph with another extent is drawn wrongly. Fixed in #NEW-A. |
| D9 | README examples use port 8765. | The default without `--port` is 8080 (`server.py:304`). | Not a conflict; the README never states a default. |
| D10 | "Chrome 157 verified the main workflow" (README). | Preparation used the Chromium 156 pane of the Claude desktop app, not Chrome itself. | The README claim stays as the owner's record. |
| D11 | `.gitignore` lists `test-results/` and `playwright-report/`. | The repository has no browser automation and the PRD allows the standard library only. | Browser checks are manual and recorded in the pull request. |

## 7. Where the planned work meets this code

- **The fixture is wired in at five places** (`routing.py:25`, 67, 72; `server.py:200`, 255). #NEW-A replaces them with a graph loaded per revision from the store while the 63 existing tests stay green, so that later tickets never touch a module constant.
- **Migrations are lists of SQL strings.** Seeding revision 1 must be literal SQL, not an import of `fixture.py`, so that history cannot change when the module does. SQLite refuses `ALTER TABLE ... ADD COLUMN ... NOT NULL DEFAULT 1 REFERENCES ...` while `foreign_keys` is on (observed on SQLite 3.50.4), and the pragma cannot be switched inside the migration transaction: add the column without `REFERENCES`, or rebuild the table.
- **Three tickets add columns to the same tables** (#4 a locality, #5 direction, seconds, penalty and an edge name, #NEW-A the tables themselves). Migration numbers are taken in merge order: the pull request that merges second renumbers its migration.
- **The dataset hash must survive those additions.** The canonical form used for `dataset_sha256` omits optional fields that have their default value, so revision 1 keeps its hash when a later ticket adds a field.
- **The page assumes a small graph.** `fillSelect` adds one option per node and `draw` walks every edge on every frame. Packs are capped at 5,000 nodes and 20,000 edges (#2). The generated 100,000-segment graph (#3) is never sent whole to the page.
- **The standard library has no browser driver.** Behaviour in the page is proved by a recorded manual run; everything that can be decided on the server is decided there and tested with `unittest`.
- **`random` is only partly stable across Python versions.** Only `random.Random(seed).random()` is guaranteed to repeat. The seeded generators in #3 and #5 use an explicit integer generator or `random()` only.
- **Console output on Windows is not UTF-8 by default** (a probe died on `cp1252` during preparation). The `verify` command in #6 prints ASCII only.

## 8. What was run during preparation

Windows 11, Python 3.13.14, SQLite 3.50.4, prep worktree at `5eb9f1f`, 2026-11-22. Nothing under `offline_routes/` or `tests/` was changed.

| Check | Result |
|---|---|
| `python -B -m unittest discover -s tests -t .` | `Ran 63 tests in 3.304s`, `OK` |
| Server on `--port 0` with a scratch data directory, driven over HTTP | `/`, `/app.css`, `/app.js` 200 with CSP, `nosniff`, `no-store`; health `{"status":"ok","version":"0.1.0","schema_version":1}`; Depot to Observatory 120 m via Library with four steps, and the reverse; Depot to Island `reachable:false`; Library to Library 0 m `Already at Library`; unknown id 404; save 201; same title in another case 409; save to Island 422; extra key 400; foreign Host 403; foreign Origin 403; 4097-byte body 413; traversal path 404 |
| Restart on the same data directory | `GET /api/v1/routes/1` returned the identical saved route |
| Page in a local Chromium 156 pane at `http://127.0.0.1:<port>/` | Calculate, save, unreachable (preview cleared, Save disabled), duplicate title (text kept, field focused), a title that looks like markup (shown as text, no `img` element), server stopped ("Server unreachable..." and title kept), restart and reopen, 800x600 and 360x640 without horizontal overflow, Tab order with a 3 px focus outline on every control. Thirteen requests, all to `127.0.0.1` |
| Processes | Each server was stopped by process id and its port confirmed free |

Not run: Python 3.12, Linux, Chrome or Firefox proper, a screen reader, contrast measurement.
