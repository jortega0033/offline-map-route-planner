# Offline Map and Route Planner

A local, single-person route planner for when live map services are unavailable. M1 routes on an original fictional graph (Depot, Library, Observatory, Island), shows an exact shortest path with ordered steps, and saves named routes in SQLite. Nothing uses the network, real addresses or geolocation.

Requires Python 3.12. No packages to install.

## Program goal

Build an offline map and routing engine for a whole country: import raw map data, draw it, route cars, bikes, walkers and public transport in milliseconds, and navigate, with no map service or routing library.

The program is planned ([#34](https://github.com/jortega0033/offline-map-route-planner/issues/34)). Phase 1 is the current epic [#1](https://github.com/jortega0033/offline-map-route-planner/issues/1) and the only phase with tickets.

**Score.** Share of random country-wide queries where the fast engine returns the same cost as a plain exhaustive search, with the median query time.

| Phase | Content | Hours (rough) | Issue |
|---|---|---|---|
| 1 | The current epic and its tickets | 46 to 74 | [#1](https://github.com/jortega0033/offline-map-route-planner/issues/1) |
| 2 | Real map data | 100 to 160 | [#35](https://github.com/jortega0033/offline-map-route-planner/issues/35) |
| 3 | Fast routing | 120 to 200 | [#36](https://github.com/jortega0033/offline-map-route-planner/issues/36) |
| 4 | Map rendering | 120 to 200 | [#37](https://github.com/jortega0033/offline-map-route-planner/issues/37) |
| 5 | Public transport | 90 to 150 | [#38](https://github.com/jortega0033/offline-map-route-planner/issues/38) |
| 6 | Search and navigation | 100 to 170 | [#39](https://github.com/jortega0033/offline-map-route-planner/issues/39) |

About 580 to 950 engineer hours in total: rough estimates, not measurements. The numbers in the score and the finish lines are targets until a run shows them. Only phase 1 has tickets to work; the sub-issues of a later phase are written when it starts. No single session is expected to reach the end.

## Launch

Linux:

```
python3 -m offline_routes --data-dir ./data --port 8765
```

Windows:

```
python -m offline_routes --data-dir .\data --port 8765
```

Then open `http://127.0.0.1:8765/`. The server binds 127.0.0.1 only. `--port 0` picks a free port and prints it. Stop with Ctrl+C. A missing data directory is created; an empty path, or a path that is a file, exits with code 2.

## M1 smoke steps

1. Open the page. Choose From = Depot and To = Observatory, press **Calculate route**.
2. Expect Depot, Library, Observatory, 120 m, with four ordered steps and the path highlighted on the map.
3. Type `Morning run` in **Route title**, press **Save route**. A button named `Morning run` appears in the saved list.
4. Change To to Island and press Calculate route. Expect "No route from Depot to Island", with the old steps and highlight cleared and Save disabled.
5. Stop the server, start it again with the same `--data-dir`, press `Morning run`. The 120 m route reopens.
6. Try saving `morning run` again. Expect a title-exists message, with your typed text kept.

## Limits

- Fixed built-in fixture graph only; no import yet.
- Write bodies are capped at 4096 bytes, titles at 80 characters, ids at 64.
- Titles must be unique, compared case-insensitively. Saved routes cannot be edited or deleted in M1.
- Loopback only; Host is checked on every request and Origin on writes; no CORS. If the port cannot be bound the process exits with code 1.

## Local persistence

Saved routes live in `<data-dir>/routes.sqlite3` (SQLite, WAL, deterministic migrations). Use a disposable directory for experiments.

## Tests

```
python -m unittest discover -s tests -t .
```

Tests use temporary directories and a random free port. See the baseline verification below for observed results.

## Planned work (not implemented)

Bounded graph-pack import with revisions, viewport pan/zoom with culling on a seeded 100k-segment fixture, landmark and licensed-address search, one-way and cost-aware routing, and revision-pinned saved routes with dataset verification. See [docs/PRD.md](docs/PRD.md).

## Baseline verification

- Windows with Python 3.13.14 and Ubuntu 24.04 WSL with Python 3.12.3 each passed 63 unit and API tests. WSL unit tests used temporary storage on tmpfs.
- A separate run on a busy WSL disk returned retryable 503 responses during concurrent saves. The tmpfs and Windows suites passed the same concurrency check.
- Chrome 157 verified the main workflow with external requests blocked. Depot to Observatory routed via Library for 120 m. An unreachable destination cleared the old route, and a saved route reopened after a server restart.
