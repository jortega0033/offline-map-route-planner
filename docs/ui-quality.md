# UI quality rules

Ten rules for every screen and every piece of user-facing text in this repository. The owner stated rules 1 and 2 and approved rules 3 to 10 on 2026-11-22; they are binding. The page is `offline_routes/static/` (`index.html`, `app.css`, `app.js`); the same rules apply to text the page builds in JavaScript and to canvas drawing.

1. No thick accent border on one side of a card, callout, alert, list item or quote (for example `border-left: 4px solid <accent>`). Use spacing, type weight, an icon or a full hairline border instead.
2. No soft tinted background with a thin border of the same hue as the default way to mark a status, tag, callout or card. One neutral surface and one clear signal (text, icon or a solid chip) is enough.
3. No gradient text and no purple-to-blue gradient as a default accent.
4. No blur or glass panels, and no drop shadow plus large radius on every card.
5. No emoji used as icons or bullets, and no sparkle marks.
6. No pill or badge on things that are not states. No all-caps, letter-spaced micro labels as section decoration.
7. No centred hero with a slogan in an application screen. Screens open on the user's task.
8. One accent colour, used for the primary action and the current selection. Status colours only for status.
9. Dense, aligned layouts on a consistent spacing scale. No card grid where a table or a list is the right form.
10. User-facing copy is plain and specific: no filler, no exclamation marks, and the same word for the same thing everywhere.

## How the rules are applied

- Colours come from the tokens described in [design-tokens.md](design-tokens.md); new UI adds no colour literal.

- A ticket that changes the page starts with the `ui-ux-pro-max` skill (`python .claude/skills/ui-ux-pro-max/scripts/search.py "<product type>" --design-system`) and ends with a check of the changed screens against this file. Where the skill's advice conflicts with these rules or with `CLAUDE.md` (no external fonts, images, CDN or framework), these rules and `CLAUDE.md` win.
- User-facing copy, documentation and pull request text go through the `unslop` skill before the pull request is opened.
- The Frontend Developer, Accessibility Auditor and Code Reviewer roles name this file in their "In this repository" checklists. Code Reviewer runs on every ticket, so the review gate is where the rules are enforced. There is no script: rule 1 could be linted, rule 2 cannot be detected reliably from CSS.
- The project accessibility rules in `docs/PRD.md` sections 9 and 11 (labels, `:focus-visible`, contrast, shape and text as well as colour) stay in force; these rules add to them.
- Changing a rule needs the owner.
