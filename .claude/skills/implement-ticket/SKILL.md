---
name: implement-ticket
description: Playbook for implementing a GitHub issue in this repository from start to pull request, with the project subagents run at fixed steps. Use whenever asked to implement, start, continue or finish a ticket, an issue or an epic child, for example "implement #12" or "work on the next ticket".
argument-hint: "[issue number]"
---

# Implement a ticket

Use this playbook for every implementation ticket in this repository. `CLAUDE.md` holds the commands, the architecture boundaries, the Git workflow and the evidence rules; where this playbook and `CLAUDE.md` differ, `CLAUDE.md` wins.

The project subagents in `.claude/agents/` are part of the work. Each role file starts with an "In this repository" section that says what the role does here and what it must be given. Delegate to them at the steps below without waiting to be asked. If a step names a role that is not installed, do that step yourself and say so in the pull request.

## Steps

1. **Read the ticket.** `gh issue view <number>` and the epic it belongs to. Check that every prerequisite issue is closed and that no owner decision named in the ticket is still open. If the ticket is blocked, stop and say what blocks it.
2. **Read the rules.** `CLAUDE.md`, then the architecture notes it links to.
3. **Orient and check the approach.** Delegate as the table "Before coding" says. Settle open design questions before writing code. For a ticket that changes `offline_routes/static/`, start with the `ui-ux-pro-max` skill (`python .claude/skills/ui-ux-pro-max/scripts/search.py "<product type>" --design-system`) and read `docs/ui-quality.md`.
4. **Branch** as the Git workflow in `CLAUDE.md` says. Never work on the default branch.
5. **Implement** inside the ticket's stated scope. Delegate the work to the implementing role that matches the files being changed (table "While coding"). Do not widen scope; note anything else you find as a follow-up. Never change `.claude/agents`, `.claude/skills`, `.claude/hooks`, `.claude/settings.json` or `.claude/agency-agents` in a ticket, also not through a shell command.
6. **Test.** Add tests for every acceptance criterion and material edge case. Expected values in existing tests stay as they are unless the issue names the test and the change (`CLAUDE.md`, "Evidence before a ticket is called done"). Then run the checks listed in `CLAUDE.md`; a change to the page also needs the recorded manual browser run it describes, because the repository has no browser automation. Record each command and its result. A criterion that needs a person ("by hand in a normal browser", "manual, recorded") is done as far as an agent can (a scripted or headless run, with the evidence); list the rest under "Owner checks" in the pull request.
7. **Specialist review.** Run every role in the table "After coding" whose trigger matches the change. For a UI change, check the changed screens against the ten rules in `docs/ui-quality.md` and fix breaches before the review gate.
8. **Copy check.** Run the `unslop` skill over user-facing copy, documentation and the pull request text you wrote, and fix what it flags.
9. **Changelog.** Add one line for the ticket under `Unreleased` in `CHANGELOG.md`.
10. **Review gate, always.** Write the diff and the check outputs to `.claude/state/review/` in the worktree first (reviewers have no shell), then run Code Reviewer on the full diff. Fix every material finding, re-run the checks, and have the reviewer look again until no material finding is left.
11. **Acceptance gate, always.** Run Reality Checker with the ticket's acceptance criteria and the evidence you produced. Do not call the ticket done unless it passes.
12. **Hand off.** Capture the evidence `CLAUDE.md` asks for. Open the pull request as a draft (`gh pr create --draft`) with `.github/pull_request_template.md` (it names the issue and has the "Agent roles run" table) only after the local checks and both gates passed on the current diff; the gate hook blocks `gh pr create` and `gh pr ready` otherwise. A `/next-ticket` run counts as the owner's request to push the branch and open the pull request; outside such a run, push and open it only when the owner asks in the current session. CI runs on the draft. If a job fails, fix it, re-run the local checks and both gates, and push. Mark the pull request ready (`gh pr ready`; the hook checks the gates again) only when `gh pr checks` is green on every job; the driver checks this, not Reality Checker. Do not poll CI: end the turn with "Draft pull request #N is waiting for CI" and read `gh pr checks` once when woken. The pull request of the last open sub-issue of a parent also says `Closes #<parent>`. Only the owner merges: never run `gh pr merge`.

## Roles

### Before coding

| Role | Access | Delegate to it |
|---|---|---|
| Codebase Onboarding Engineer | read-only reviewer | At the start of a ticket in an unfamiliar area, to trace the relevant code paths before anything is changed |
| Software Architect | read-only reviewer | Before implementing a ticket that adds or changes a module boundary, data model, storage schema, public API or dependency, to check the approach against the architecture notes |

### While coding

| Role | Access | Delegate to it |
|---|---|---|
| Backend Architect | can edit | When a ticket changes server-side code, HTTP routes, validation, persistence or data migrations |
| Database Optimizer | read-only reviewer | When a ticket changes SQL, the schema, indexes or query paths |
| Frontend Developer | can edit | When a ticket changes browser-side code such as pages, components, client state, styling or keyboard interaction |

### After coding

| Role | Access | Delegate to it |
|---|---|---|
| Application Security Engineer | read-only reviewer | After a ticket touches input parsing, file upload or import, sanitization, origin and host checks, or any handling of untrusted data |
| Accessibility Auditor | read-only reviewer | After a ticket changes user-facing UI, keyboard handling, focus order or markup |
| API Tester | can edit | After a ticket adds or changes an HTTP endpoint, status code or request and response contract |
| Performance Benchmarker | read-only reviewer | After a ticket with a performance budget, a benchmark or large-input behaviour |

### Gates that run on every ticket

| Role | Access | Delegate to it |
|---|---|---|
| Code Reviewer | read-only reviewer | After implementing or changing code for a ticket, before the work is called done or a pull request is opened |
| Reality Checker | read-only reviewer | As the acceptance gate of every ticket, after Code Reviewer and before the draft pull request is opened, to check each acceptance criterion against the local evidence that was actually produced, and that CI is configured to run the checks |

## Rules

- The session or role that wrote a change does not count as its reviewer.
- Read-only reviewers cannot run commands. Give them the diff, the acceptance criteria and the recorded command output.
- Where a role's general advice (frameworks, dependencies, cloud services) conflicts with `CLAUDE.md`, `CLAUDE.md` wins.
- In the pull request description, add a section "Agent roles run" listing each role that ran, what it was asked and its verdict, and any step you did yourself because a role was missing.
