# Releasing

Only the owner releases. An agent never tags, publishes or creates a release.

## What a release is here

A tag on `main` and a GitHub release for it. There is no package registry, no build step and no artifact: the program is the source tree, run with `python -m offline_routes`. The version string lives in `offline_routes/__init__.py` (`__version__`, reported by `/api/v1/health` and asserted in `tests/test_api.py`, `docs/PRD.md` and `docs/architecture.md`).

## Steps

1. Start from an up-to-date `main` with CI green on its latest commit.
2. Run `python -m unittest discover -s tests -t .` from a clean checkout. The last line must be `OK`.
3. Run the smoke steps in `README.md` on a scratch data directory (`--port 0`), and stop the server afterwards.
4. Move the `Unreleased` entries of `CHANGELOG.md` under a new heading `## [x.y.z] - YYYY-MM-DD` and leave an empty `Unreleased` section.
5. If the version changes, update `__version__` and every place that quotes it (the test above, `docs/PRD.md`, `docs/architecture.md`, `CLAUDE.md`) in the same pull request, and merge it.
6. Tag the merge commit: `git tag -a vX.Y.Z -m "vX.Y.Z"` and `git push origin vX.Y.Z`.
7. Create the GitHub release from the tag, with the changelog section as its notes.
