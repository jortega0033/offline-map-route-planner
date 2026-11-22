# Agency Agents roles used in this repository

The Markdown files in `.claude/agents/` whose names start with `engineering-`, `security-` or `testing-` are copies of role definitions from Agency Agents. They are project-local Claude Code subagents. The file `loop-verifier.md` in the same folder is not from Agency Agents; it belongs to the Loop Engineering setup described in [`LOOP.md`](../../LOOP.md).

## Source and licence

- Upstream: https://github.com/msitarzewski/agency-agents
- Pinned revision: `8ae6164602c95ca78828b148b9052460ee426885` (upstream `main`, committed 2026-11-09)
- Licence: MIT, "Copyright (c) 2025 AgentLand Contributors". The upstream licence text at the pinned revision is kept unchanged in [`LICENSE`](LICENSE) next to this file (SHA-256 `9a45258434d5cedf0af73c9ad4771373701225038d246c49219026c33677f66f`). It covers only the copied role files, not the rest of this repository.
- Fetched with `gh api -H "Accept: application/vnd.github.raw" "repos/msitarzewski/agency-agents/contents/<path>?ref=<revision>"`.

## Installed roles

"Upstream SHA-256" is the hash of the file as fetched at the pinned revision. Reviewer roles have one added frontmatter line, `tools: Read, Grep, Glob`, so they cannot edit files or run commands. Nothing else in any file was changed.

| File in `.claude/agents/` | `name:` | Upstream path | Upstream SHA-256 | Local change |
|---|---|---|---|---|
| `engineering-software-architect.md` | Software Architect | `engineering/engineering-software-architect.md` | `b85121691776147bacde26673e68fbbacd6a7f0816d1ca8e203c264d25ce1d30` | added `tools: Read, Grep, Glob` |
| `engineering-code-reviewer.md` | Code Reviewer | `engineering/engineering-code-reviewer.md` | `7509fcc3ea1dda46511b2801996305bf3d4a125576f9655ff0b63df25602f446` | added `tools: Read, Grep, Glob` |
| `engineering-codebase-onboarding-engineer.md` | Codebase Onboarding Engineer | `engineering/engineering-codebase-onboarding-engineer.md` | `07aa548b45887c3ad768efad5fdbf6e57bea639df4f1b74c7e383142f454e2a1` | added `tools: Read, Grep, Glob` |
| `engineering-database-optimizer.md` | Database Optimizer | `engineering/engineering-database-optimizer.md` | `6d773003e3b9251068ab537be94d6827c118201e0e17c11d789cb29dc245bf99` | added `tools: Read, Grep, Glob` |
| `security-appsec-engineer.md` | Application Security Engineer | `security/security-appsec-engineer.md` | `a19f0bda46f4adca5737365dbc3c7ed93e9d93b71349536d92ff055dcf4e3b83` | added `tools: Read, Grep, Glob` |
| `testing-accessibility-auditor.md` | Accessibility Auditor | `testing/testing-accessibility-auditor.md` | `362935907af23839775b9c6162f38c0c5a740542ab4350cb5c5b5a0d9f9a4268` | added `tools: Read, Grep, Glob` |
| `testing-reality-checker.md` | Reality Checker | `testing/testing-reality-checker.md` | `6d32fcdb114233e13902ec6372d50293b120e85d490b5e81d372c29808f988a1` | added `tools: Read, Grep, Glob` |
| `testing-performance-benchmarker.md` | Performance Benchmarker | `testing/testing-performance-benchmarker.md` | `16a841f67392d084b773c6d9f05341d093e9017f3e116f6df0de59a5a3f59c34` | added `tools: Read, Grep, Glob` |
| `engineering-backend-architect.md` | Backend Architect | `engineering/engineering-backend-architect.md` | `ac717bde4848d7663fff8a3c7edc711fd119256de6a7ce38c036619372f42c99` | none |
| `engineering-frontend-developer.md` | Frontend Developer | `engineering/engineering-frontend-developer.md` | `1ae4cc10b2e0163bd3ed921ad54080b865cd02e591becd8919b64b73fab06dad` | none |
| `testing-api-tester.md` | API Tester | `testing/testing-api-tester.md` | `ab91de9188d48bd9c417282c33673a37b066215e90e08c0f1b270d036084e3bb` | none |

## Why these roles

| Role | Use in this repository |
|---|---|
| Software Architect (read-only) | Review a ticket's design against the layering in [`docs/architecture.md`](../../docs/architecture.md) before code is written: where pack validation, the graph generator, the search index and the `verify` command live, how a revision stays immutable, how a per-route body cap fits the request guards. |
| Code Reviewer (read-only) | Review a diff for correctness, missed edge cases and broken rules (request guards on new routes, no traceback in responses, limits enforced on the server, deterministic output, forward-only migrations). |
| Codebase Onboarding Engineer (read-only) | Trace a code path and report facts with file and line citations. |
| Database Optimizer (read-only) | Review schema changes, migrations, indexes and transaction scope in `offline_routes/store.py`. The planned tickets add revision, node and edge tables, bulk inserts of up to 100,000 rows in one transaction, and bounding-box lookups. |
| Application Security Engineer (read-only) | Review the parts where untrusted input meets the server or the page: the graph-pack import (size cap before reading, shape validation, no partial writes), query-string parsing on the new GET routes, any new mutating route (Host and Origin checks), and names from a pack reaching the page as text only. |
| Accessibility Auditor (read-only) | Review keyboard operation, focus, labels, live regions and text equivalents. The planned work adds a file input, a revision selector, a combobox with listbox semantics and pan and zoom controls on a canvas. |
| Performance Benchmarker (read-only) | Review how the 100,000-segment work is measured and bounded: the feature cap, what the page draws per frame, import and query cost, and whether a claimed measurement was actually taken. It cannot run anything itself. |
| Reality Checker (read-only) | Compare claimed evidence with what was actually run before a ticket or the epic is called done. |
| Backend Architect | Implement work in `offline_routes/*.py` (HTTP layer, store and migrations, routing, pack validation, generator, search, `verify`). |
| Frontend Developer | Implement work in `offline_routes/static/`. |
| API Tester | Write the HTTP-level `unittest` cases in `tests/` for new and existing routes. |

Most of these roles are written for larger stacks. Backend Architect, Frontend Developer and API Tester mention frameworks, cloud services and Playwright; Database Optimizer is written around PostgreSQL and MySQL; Application Security Engineer describes scanners and pipelines; Performance Benchmarker describes load-testing tools. In this repository the rules in [`CLAUDE.md`](../../CLAUDE.md) win: Python standard library only, SQLite, native HTML, CSS and JavaScript, `unittest`, no pip or npm dependencies, no external requests.

Roles that were considered and left out: the `gis/` division (Web GIS Developer is written for MapLibre, Leaflet and ArcGIS, Spatial Data Engineer and GIS QA Engineer for real geospatial formats and coordinate systems; this product has no tiles, no map library and no real-world data), Search Relevance Engineer (written for Elasticsearch and OpenSearch; the planned index is a small deterministic ranking with its own acceptance criteria), Data Visualization Engineer (charting libraries), Test Automation Engineer and Evidence Collector (their methods need tools this repository does not allow; browser checks are manual and recorded).

## Name collision with user-level agents

A developer who has installed Agency Agents in `~/.claude/agents/` already has agents with the same `name:` values. Claude Code gives the project-level definition precedence, so inside this repository the copies here are used, including the read-only tool limits. The upstream names were kept on purpose so that the roles stay recognisable and can be compared with upstream.

A Claude Code session that was already running when these files were added keeps the definitions it loaded at start. Start a new session to pick up the project copies.

## Check that the roles load

From the repository root, in a new session:

```text
claude -p "List the project-level subagents defined in .claude/agents with the tools each one may use. Then run the Reality Checker subagent and ask it which tools it has."
```

The eight reviewer roles and `loop-verifier` must report exactly `Read, Grep, Glob`.

### What was observed, and what was not

Observed on 2026-11-22 with Claude Code 2.1.323, headless (`claude -p`, model requested: haiku, no MCP servers), from the repository root, on a machine that also has a user-level Agency Agents install:

- All twelve names were listed (the eleven roles above and `loop-verifier`). Software Architect, Code Reviewer, Codebase Onboarding Engineer, Database Optimizer, Application Security Engineer, Accessibility Auditor, Performance Benchmarker, Reality Checker and `loop-verifier` were listed with `Read, Grep, Glob`. Backend Architect, Frontend Developer and API Tester were listed with all tools.
- A launched Reality Checker and a launched Performance Benchmarker each reported exactly `Read`, `Grep`, `Glob`. The user-level copies of the reviewer roles on that machine have no `tools:` line, so the tool limits show that the project copies were the ones loaded.
- The user-level copies of the three implementing roles on that machine are a different upstream revision with different example code. Each role was launched and asked to quote its own instructions, and each quoted text that exists only in the project copy: Backend Architect listed the tables `users`, `categories`, `products` (the user-level copy has no `categories` table), Frontend Developer quoted the comment "Renderable cell values and stable IDs keep the example self-contained.", and API Tester quoted `import { randomUUID } from 'node:crypto';`. This shows project precedence for these three on that machine.
- **Not shown:** behaviour in an interactive session, and behaviour on a machine without a user-level install (there the names must simply be listed).
- The listing gives names and tools only, not the file a definition comes from. The statements above about which copy was loaded rest on the tool limits and the quoted text.

## Updating

Fetch the same paths at a newer revision, re-apply the `tools:` line to the eight reviewer roles, and update the revision and hashes in this file in the same commit.

## Local change: automatic delegation (2026-11-22)

One sentence beginning "Use proactively" was appended to the `description:` line of every Agency Agents role in `.claude/agents/` (not to `loop-verifier`). Claude Code uses that field to decide when to delegate, so the roles now run during ticket work without being named.

A section headed `## In this repository` was then inserted in every Agency Agents role file (again not in `loop-verifier`), directly after the closing `---` of the frontmatter and before the upstream text. It is project-specific text written for this repository, not upstream text: the project and its hard rules, the files the role owns or reviews, its commands or the output it must be given, a checklist that cites `CLAUDE.md`, `docs/architecture.md` and `docs/PRD.md`, the parts of the upstream text that do not apply here, and what the role hands back. It ends with the sentence "This section and CLAUDE.md override the generic text below wherever they differ." The upstream text below it is unchanged. When one of the cited documents changes, the sections that cite it must be checked in the same pull request.

This supersedes any statement above that a role file is unmodified, that the `tools:` line is the only local change, or that nothing else was changed, including the "Local change" column of the table. To compare a role with the pinned upstream file, first remove three things: the "Use proactively" sentence, the `tools:` line where one was added, and the whole "In this repository" section with the blank line that follows it. When updating to a newer upstream revision, re-apply all three.

The steps at which each role runs are in `.claude/skills/implement-ticket/SKILL.md`.

Verification (2026-11-22): after the sections were inserted, `claude -p "List every project subagent defined in .claude/agents with its exact name and tools, say for each whether its instructions begin with a section titled In this repository, and say whether a skill named implement-ticket is available. Plain list, no commentary." --model haiku` was run once from the repository root with Claude Code 2.1.323. It listed all twelve names. The eight reviewer roles and `loop-verifier` were listed with `Read, Grep, Glob`; Backend Architect, Frontend Developer and API Tester with no `tools` field, so all tools. It answered "Yes" for the "In this repository" section on each of the eleven Agency Agents roles and "No" for `loop-verifier`, and reported the `implement-ticket` skill as available. The answer named the files, so the model may have read them from disk instead of reporting its loaded definitions; no role was launched in this check. A byte comparison made at the same time showed that each role file equals the previous commit once the inserted section is removed.

## Local change: SDLC kit (2026-11-22)

This pass added, without changing any role's upstream text: one checklist line in Frontend Developer, Accessibility Auditor and Code Reviewer that names `docs/ui-quality.md` (UI Designer and UX Architect are not installed here); the review gate hook `.claude/hooks/role_gate.py` with gate roles Code Reviewer and Reality Checker, wired in `.claude/settings.json`; the `next-ticket` driver and the updated `implement-ticket` playbook; the `ui-ux-pro-max` and `unslop` skills with their `PROVENANCE.md` files; and `docs/ui-quality.md`, `docs/owner-decisions.md`, CI, the pull request template, `CODEOWNERS`, the ticket template, Dependabot for GitHub Actions, `SECURITY.md`, `CHANGELOG.md` and `docs/RELEASING.md`. No role was added or removed, so the table of installed roles above is unchanged.
