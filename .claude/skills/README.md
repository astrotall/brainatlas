# Skills — global

Skills are organised by scope. This directory holds **global** skills: cross-cutting ones that
apply to the whole repo, both the site and the API.

Claude Code discovers skills in every `.claude/skills/` directory and offers all of them:

| Scope       | Location                  | Loads                         |
| ----------- | ------------------------- | ----------------------------- |
| **Global**  | `.claude/skills/` (here)  | everywhere                    |
| **Backend** | `backend/.claude/skills/` | when working under `backend/` |

Scoped skills are offered with a path prefix (e.g. `backend:<name>`), and a scoped skill wins over
a global one of the same name when you are working in that directory. The frontend lives at the
repo root (`app/`, `src/`), so frontend skills go here.

Put a skill here when it applies to the whole repo or to the frontend. If it targets only the
Python API — ports and adapters, FastAPI, Redis, the moderation webhook, the translation step — put
it in `backend/.claude/skills/` so it does not surface where it is irrelevant. That directory is
created with its first skill.

Skills follow the same scopes as commits (`web`, `ui`, `atlas`, `api`, `reviews`, `stats`, `i18n`,
`deps`, `ci`, `docs`, `infra`): name a skill after what it does, and say in its description which
of those areas it covers.

## Current global skills

- **[`edge-case-bug-hunting`](edge-case-bug-hunting/SKILL.md)** — adversarial QA: boundary-value
  analysis, destructive/negative testing, pairwise, state-transition and mutation gaps, then
  writes failing regression tests. Cross-cutting: it covers the public surface and legacy URLs
  (`web`, `infra`), the reviews and stats API (`api`, `reviews`, `stats`), and the translation
  step, so it lives here.
