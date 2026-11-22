# CLAUDE.md

Working instructions for this repository. Read this file first, then the documents it links to. It does not repeat them.

## What this is

An offline route planner for one person on one computer. One Python package, standard library only, serves a JSON API and a static page on `127.0.0.1` and keeps saved routes in one SQLite file. M1 is implemented: a built-in fictional graph of four landmarks, exact shortest path with ordered steps, saving a named route, reopening it after a restart. Importing graph packs, large-graph pan and zoom, place search, one-way and cost-aware routing, and verification of saved routes are planned and tracked in the epic, issue #1.

## Sources of truth

| Topic | Document |
|---|---|
| Product scope, milestones, API and schema contracts, fixtures, acceptance matrix | [docs/PRD.md](docs/PRD.md) |
| How the code is built, the traced workflow, the rules the code keeps, differences between the PRD and the code | [docs/architecture.md](docs/architecture.md) |
| Launch, smoke steps, limits, the owner's baseline verification | [README.md](README.md) |
| Backlog | Epic issue #1 and its sub-issues on GitHub, in dependency order: #7, #2, then two tracks (#4 then #3, and #5 then #6), then #8. The epic gives the dependencies, the join points and the estimates. |
| Loop setup and its limits | [LOOP.md](LOOP.md), [loop-constraints.md](loop-constraints.md) |
| Project subagents and their origin | [.claude/agency-agents/README.md](.claude/agency-agents/README.md) |
| Ticket playbook | [.claude/skills/implement-ticket/SKILL.md](.claude/skills/implement-ticket/SKILL.md) |
| UI rules | [docs/ui-quality.md](docs/ui-quality.md) |
| Owner decisions | [docs/owner-decisions.md](docs/owner-decisions.md) |

When the PRD and the code disagree, the code is the baseline and [docs/architecture.md](docs/architecture.md) records the difference. A ticket that changes a contract updates the PRD section that states it (6 for the API, 7 for the schema, 8 for the algorithm, 9 for the page) in the same pull request.

## Setup

Python 3.12 or newer. Nothing to install: there is no package manifest, no virtual environment requirement, no build step and no lint step. On Windows the interpreter is `python`; on Linux it is `python3`. Do not use a language feature or library call that needs more than 3.12.

## Commands

All of them were run during preparation on Windows 11 with Python 3.13.14, from the repository root (the server on port 0 and on port 18795 with a scratch data directory instead of the values shown).

Run the tests (63 tests, about 4 seconds):

```
python -m unittest discover -s tests -t .
```

The run is good when the last line is `OK`. Add `-B` (`python -B -m unittest ...`) to keep `__pycache__` out of the tree.

A single test: `python -m unittest tests.test_routing.RoutingTests.test_depot_to_observatory`.

Run the server (binds `127.0.0.1` only; `--data-dir` is required and is created if missing; stop with Ctrl+C):

```
python -m offline_routes --data-dir ./data --port 8765
```

`--port 0` picks a free port and prints it. Without `--port` the default is 8080. The process prints `Serving on http://127.0.0.1:<port>/`. `data/` and `*.sqlite*` are ignored by Git; for experiments use a scratch directory outside the repository and delete it afterwards.

Quick check that a running server answers:

```
curl -s http://127.0.0.1:8765/api/v1/health
```

Expected: `{"status":"ok","version":"0.1.0","schema_version":1}`.

On Windows, `python` can be a launcher that starts the real interpreter as a child, so the process id a shell reports is not always the one that holds the port, and `kill` from Git Bash can leave the server running. Find the listener with `netstat -ano | grep :<port>`, stop it with `taskkill //PID <pid> //F` (or `Stop-Process -Id <pid>`), then confirm that nothing listens on the port. Stop only processes you started.

## Hard rules

These come from PRD sections 2, 5 and 12. A change that breaks one needs the owner's approval first, not a pull request.

- Standard library only, in the application and in the tests. No pip or npm dependency, no build tooling, no CDN, font, image, map tile or script from another host.
- Loopback only. The server binds `127.0.0.1`. No CORS headers. No outgoing request from the server, the page or the tests.
- No external map service, no geolocation, no accounts, sign-in, remote sync, hosting or model integration.
- Graph and address data in the repository is synthetic and written for this repository. Real-world extracts and third-party data are out of scope until the owner approves a source and its licence (PRD section 14).
- Text is data. It reaches the page through `textContent`, `value` or DOM nodes built with `createElement`, never through `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` or `eval`. No inline script or style: the CSP forbids it.
- Static files are served from the fixed allowlist in `offline_routes/server.py`. Request input is never joined into a file path.
- Tests use a temporary directory and port 0. No fixed port, no network, no dependence on wall-clock timing for a pass.

## Architecture boundaries

Details, line references and the full list of rules are in [docs/architecture.md](docs/architecture.md). The short form:

- `offline_routes/server.py`: command line and HTTP. Request guards (Host, Origin, body length cap, media type), static allowlist, security headers, JSON envelope, input validation, mapping of errors to status codes. It never runs SQL and never computes a route itself.
- `offline_routes/routing.py`: the algorithm and the step texts. Pure functions. No HTTP, no SQL.
- `offline_routes/fixture.py`: the built-in graph `fixture-v1`. Saved routes refer to it; do not edit its nodes, edges or id.
- `offline_routes/store.py`: the only module that reads or writes application data in SQLite. Ordered forward-only migrations, one short-lived connection per operation. It never touches HTTP objects.
- `offline_routes/static/`: one page, native JavaScript, no framework. It talks to the server through `/api/v1` only and stores nothing in the browser.
- `tests/`: `unittest`. `test_routing.py` calls the algorithm, `test_store.py` drives the store, the migrations and `main`, `test_api.py` drives a real server on port 0 over `http.client`.

Keep new code on the correct side of these lines. A new module is fine when a file would otherwise take on a second job (for example pack validation, a graph generator, a search index or the `verify` command).

Rules that every change must keep:

- The server computes; the page displays. A request never supplies a path, a distance or a cost.
- Existing databases open under new code. A schema change is a new entry at the end of `MIGRATIONS`, never an edit of an old one, with a test that opens a database made by the previous version. A database newer than the code is refused untouched and the process exits with 2.
- A stored graph revision never changes after it is written, and a saved route keeps showing the result it was saved with.
- Every route checks `Host`. Every mutating route also checks `Origin`. Error responses use the envelope `{"error":{"code","message"}}` and never contain a traceback.
- Limits stay enforced on the server: 4096 bytes per request body unless a route documents its own cap, titles 1 to 80 characters, ids 1 to 64.
- Routing is deterministic: the same graph and the same request give byte-identical JSON.
- A stale result is never left on screen: any change of selection, error or unreachable answer clears the preview and disables Save.

## Git workflow

- `main` is the default branch. CI runs the test suite on Linux and Windows (see "Delivery workflow"); checks are also run locally and reported with their output.
- One branch per issue. The repository has no naming rule yet; `<issue-number>-<short-slug>` is the suggested form. Small commits with imperative subjects and a type prefix, as in the existing history (`feat:`, and by extension `fix:`, `docs:`, `test:`, `chore:`).
- Open a pull request that names the issue (`Part of #1`, `Closes #n`) with the pull request template. Push the branch and open it only when the owner asked in the current session; a `/next-ticket` run counts as that request. Open or ready it only after both gates passed on the current diff and, for ready, CI is green. Do not merge your own pull request and do not push to `main`.
- Two pull requests that each add a migration: the one that merges second renumbers its migration and rebases.
- Never commit a data directory, a SQLite file, `.env*`, or `.prep/`.
- Do not change `.claude/agents/`, `LOOP.md`, `loop-constraints.md` or `loop-budget.md` as part of a feature ticket.

## Evidence before a ticket is called done

Put these in the pull request description. Paste real output; do not summarise a run you did not make.

1. The output tail of `python -m unittest discover -s tests -t .` from a clean checkout, with the Python version and the operating system. State the test count before and after the change. List every line changed in an existing test and why; expected values in existing tests stay as they are unless the issue names the test and the change.
2. For each acceptance criterion of the issue: the name of the test that proves it, or the exact manual step and what was observed.
3. For a schema change: the test that opens a database created by the previous schema version, the new `schema_version` reported by `/api/v1/health`, and proof that a route saved before the change reopens unchanged.
4. For a new or changed route: one request and response pair per success and per error code, taken from a server started with `--port 0` on a scratch data directory, and the diff of PRD section 6.
5. For a change under `offline_routes/static/`: a browser run on `http://127.0.0.1:<port>/` with the browser name and version, the viewport sizes checked (800x600 and 360x640), keyboard-only operation of the changed controls, and the console and network log free of errors and of requests to another host. Browser checks are manual: the repository has no approved browser automation.
6. For anything that claims determinism (routing, generators, search order, `verify` output): the same result from two runs, and the pinned expected value in a test.
7. `git status` showing no stray files, and confirmation that no dependency, external URL or non-loopback listener was added.
8. Green CI on the pull request: every job of `.github/workflows/ci.yml` passed.
9. Anything not verified, said plainly (for example "not run on Linux" or "not run on Python 3.12").

## Subagents and ticket work

Project roles live in `.claude/agents/`. Each Agency Agents role file starts with an "In this repository" section written for this project: the stack and the hard rules that bind the role, the files it owns or reviews, its commands (or the output it must be given), its checklist and what it hands back. That section and this file override the generic upstream text below it. Sources, licence, local changes and the name collision with a user-level install are in [.claude/agency-agents/README.md](.claude/agency-agents/README.md).

When asked to implement, continue or finish a GitHub issue, follow the playbook in [`.claude/skills/implement-ticket/SKILL.md`](.claude/skills/implement-ticket/SKILL.md). Claude Code loads it on its own for ticket work; `/implement-ticket <issue number>` starts it by hand. Delegate to the roles without waiting to be asked: each role's `description` ends with a "Use proactively ..." sentence, which is what makes Claude Code do so. The playbook gives each role's trigger; the short form:

| When | Roles | Access |
|---|---|---|
| Before coding | Codebase Onboarding Engineer, Software Architect | `Read, Grep, Glob` |
| While coding | Backend Architect (`offline_routes/*.py`), Frontend Developer (`offline_routes/static/`) | can edit |
| While coding | Database Optimizer (SQL, schema, migrations) | `Read, Grep, Glob` |
| After coding, when the trigger matches | Application Security Engineer, Accessibility Auditor, Performance Benchmarker | `Read, Grep, Glob` |
| After coding, when the trigger matches | API Tester (HTTP-level tests in `tests/`) | can edit |
| Gates on every ticket, however small | Code Reviewer on the full diff (review gate), then Reality Checker on the acceptance criteria and the evidence (acceptance gate) | `Read, Grep, Glob` |

- A role limited to `Read, Grep, Glob` cannot run commands: give it the diff, the acceptance criteria and the recorded command output.
- The session or role that wrote a change does not count as its reviewer.
- List the roles that ran and their verdicts in the pull request description under "Agent roles run".
- `loop-verifier` is also limited to `Read, Grep, Glob`. It belongs to the Loop and has no part in ticket work.

## Delivery workflow

How a ticket gets from the backlog to a ready pull request. Each piece lives in its own file; this part only links them.

- **Start and playbook.** The owner starts one ticket with `/next-ticket` ([.claude/skills/next-ticket/SKILL.md](.claude/skills/next-ticket/SKILL.md)); it runs [.claude/skills/implement-ticket/SKILL.md](.claude/skills/implement-ticket/SKILL.md). Nothing is scheduled. [LOOP.md](LOOP.md) says why ticket work is not a loop run.
- **Review gate hook.** [.claude/hooks/role_gate.py](.claude/hooks/role_gate.py), wired in [.claude/settings.json](.claude/settings.json), blocks `gh pr create` and `gh pr ready` until Code Reviewer and Reality Checker ran after the last code edit. Starting Claude Code with `ROLE_GATE=off` in its environment switches it off for that session.
- **Permissions.** The allow, ask and deny rules are in `.claude/settings.json`. Edits to CI, agent configuration and Loop files ask first; force pushes, pushes to `main`, `gh pr merge`, releases and reads of `.env` are denied.
- **CI.** [.github/workflows/ci.yml](.github/workflows/ci.yml) must be green: job `test` on Ubuntu and Windows with Python 3.12 and 3.13.
- **Pull request.** [.github/pull_request_template.md](.github/pull_request_template.md). Labels on tickets: `status:ready`, `status:blocked`, `status:in-progress`, `needs-decision`.
- **Changelog.** Every ticket pull request adds a line under `Unreleased` in [CHANGELOG.md](CHANGELOG.md). Releasing is in [docs/RELEASING.md](docs/RELEASING.md); security reports in [SECURITY.md](SECURITY.md).
- **UI and writing.** [docs/ui-quality.md](docs/ui-quality.md) holds the ten UI rules; the `ui-ux-pro-max` and `unslop` skills are in `.claude/skills/`.
- **Decisions.** [docs/owner-decisions.md](docs/owner-decisions.md) records what the owner decided and where it is implemented.
- **Merge.** Only the owner merges and releases.

## Loop

Issue triage runs at L1: report-only, started by hand, no scheduler, no GitHub writes. See [LOOP.md](LOOP.md).
