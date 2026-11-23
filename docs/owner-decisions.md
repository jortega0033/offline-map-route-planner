# Owner decisions

Decisions the owner made for this repository on 2026-11-22, so the rules do not depend on anyone's memory of a conversation. Changing any entry needs the owner. An agent that finds a decision blocking a ticket stops and says so.

Decision 11 (Rust verified in CI only) does not apply: this repository has no Rust code.

## 1. The instructions, tooling and playbook live on the default branch

- Date: 2026-11-22
- Implemented in: `CLAUDE.md` (Delivery workflow), `.claude/skills/implement-ticket/SKILL.md`, `.claude/skills/next-ticket/SKILL.md`, `.claude/hooks/role_gate.py`, `.claude/settings.json`; installed by merging the preparation branch into `main`.

## 2. Persona agents run automatically during ticket work and carry instructions tailored to this project

- Date: 2026-11-22
- Implemented in: `.claude/agents/*.md` ("Use proactively" in each `description`, "In this repository" section), `.claude/agency-agents/README.md`, `.claude/skills/implement-ticket/SKILL.md`.

## 3. Every open ticket is about app implementation; tooling is installed, not ticketed

- Date: 2026-11-22
- Implemented in: this kit (`.claude/`, `.github/`, `docs/`); epic #1 and its children #2 to #8 contain only application work.

## 4. Agents may take a ticket up to a ready pull request; only the owner merges and releases

- Date: 2026-11-22
- Implemented in: `CLAUDE.md` (Git workflow, Delivery workflow), `.claude/skills/next-ticket/SKILL.md`, `.claude/skills/implement-ticket/SKILL.md` (step 12), `.claude/settings.json` (`gh pr merge` and `gh release create` denied), `docs/RELEASING.md`.

## 5. No scheduler; ticket work starts only on the owner's go signal (`/next-ticket`), because the repository is used to train AI models

- Date: 2026-11-22
- Implemented in: `.claude/skills/next-ticket/SKILL.md` (`disable-model-invocation: true`), `LOOP.md`, `AGENTS.md`.

## 6. A review gate hook blocks opening or readying a pull request until the gate roles have run after the last code edit

- Date: 2026-11-22
- Implemented in: `.claude/hooks/role_gate.py` (gate roles Code Reviewer and Reality Checker), `.claude/settings.json` (`hooks`), `.github/workflows/ci.yml` (hook self-test).

## 7. Loop Engineering stays at L1, report-only and unscheduled

- Date: 2026-11-22
- Implemented in: `LOOP.md` ("Operating level", "Ticket work is not a loop run"), `loop-constraints.md`, `loop-budget.md`.

## 8. Continuous integration runs on Linux and Windows; the default branch requires a pull request and green checks

- Date: 2026-11-22
- Implemented in: `.github/workflows/ci.yml` (job `test`, Ubuntu and Windows, Python 3.12 and 3.13). Branch protection is set on GitHub by the orchestrator and owner, not by a file in the repository.

## 9. Permission rules

Documented commands are allowed; force pushes, pushes to the default branch, merges, releases and reads of secrets are denied; edits to CI, agent configuration and Loop files ask first.

- Date: 2026-11-22
- Implemented in: `.claude/settings.json` (`permissions`).

## 10. Open decisions on tickets are settled with the ticket's stated default

- Date: 2026-11-22
- Implemented in: the table below, and the same text on each issue. Epic #1 states each default and says the owner can overrule one by editing that ticket before work starts.

| Issue | Open choice (PRD section 15) | Default taken |
|---|---|---|
| #4 | Combobox or select for many landmarks | One combobox with listbox semantics for every graph size; it also lists the first places when the field is empty. The selects stay until #4. |
| #5 | Fastest profile: speed or seconds | An optional integer `seconds` per edge; an edge without it counts `meters` seconds (a nominal 1 m/s). |
| #7, #6 | Store path and steps, or recompute on reopen | Stored. Reopen shows the stored result; `verify` and Recalculate recompute and compare, and never overwrite. |
| #3 | Features from SQL range queries or an in-memory grid | An in-memory uniform grid per revision, built on first use and kept; not SQLite R*Tree. |
| #6 | Meaning of "current revision" | The `current` value of `GET /api/v1/revisions` (the highest revision number), not the revision selected in the page. |

## 12. The ten UI rules are binding, and the `ui-ux-pro-max` and `unslop` skills are used for UI work and copy

- Date: 2026-11-22
- Implemented in: `docs/ui-quality.md`, `.claude/skills/ui-ux-pro-max/`, `.claude/skills/unslop/` (each with `PROVENANCE.md`), `.claude/skills/implement-ticket/SKILL.md`, `.claude/settings.json` (search script allowed).

## 13. Visual system: Pipenzo Flow look tokens (docs/design-tokens.md). SDLC kit version: jortega0033/sdlc-kit v1.0.0.

- Date: 2026-11-23
- Implemented in: `offline_routes/static/tokens.css`, `offline_routes/static/app.css`, `offline_routes/static/app.js`, `docs/design-tokens.md`.
- Geometry kept as before (2px borders, offset panel shadow, 3px total rule, dashed save divider); only colours map to tokens. One owner-check item: the `#status` message lost its 4px left accent border and padding, because that breaches UI rule 1 in `docs/ui-quality.md`; the error state is now shown by colour and weight only.
