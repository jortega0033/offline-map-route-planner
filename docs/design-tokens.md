# Design tokens

The page uses the Pipenzo "Flow look" tokens: black page, Flow-style alpha layers, one accent (Pipenzo yellow `#FECE02`), red only for danger. Dark is the primary design; the light block is the matching light theme.

- **Source:** `jortega0033/clip-to-reel-studio`, `extension/sidepanel/tokens.css`, commit `a13378ce73e5b27213c9a200fc960ec93afef054` (2026-11-21). The copy is `offline_routes/static/tokens.css`, served at `/tokens.css` (listed in `STATIC_FILES` in `offline_routes/server.py`).
- **Resync:** copy the source file over `offline_routes/static/tokens.css`. Do not edit the copy and do nothing else.
- **Rule:** new UI uses these tokens; no new colour literals in CSS or JavaScript. Canvas code reads them with `getComputedStyle(document.documentElement).getPropertyValue('--token')`.
- **Light and dark:** the operating system colour scheme (`prefers-color-scheme`) chooses the block. The map redraws when it changes.
- **Yellow:** only on the primary action and the current selection (the highlighted route). Text never sits on a bare alpha layer; use the solid tokens.

## Tokens by role

| Role | Tokens |
|---|---|
| Surfaces | `--bg`, `--bg-raised`, `--surface`, `--bg-sunken` |
| Text | `--fg`, `--muted`, `--faint`, `--on-ink`, `--on-ink-muted`, `--on-media` |
| Lines | `--border`, `--hairline`, `--control-border`, `--input-border` |
| Accent | `--primary`, `--primary-press`, `--primary-edge`, `--on-primary`, `--focus`, `--ring-accent` |
| Status | `--danger`, `--danger-bg`, `--success`, `--ok`, `--ok-bg`, `--warn-fg`, `--warn-bg`, `--info` |
| Interaction layers | `--state-hover`, `--state-selected`, `--btn-secondary`, `--btn-secondary-border` |
| Hero, glass, scrim | `--hero-*`, `--glass*`, `--scrim`, `--ink*` |
| Shadow, gradient | `--shadow-1` to `--shadow-3`, `--shadow-float`, `--grad-*` |
| Type, space, shape, motion | `--font`, `--font-display`, `--mono`, `--space-1` to `--space-7`, `--radius-*`, `--dur-*`, `--ease-*` |
