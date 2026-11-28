# CLAUDE.md

Instructions for Claude working in this repository. Read this file first, then the detailed
guides in `.claude/docs/` and `.claude/backend/` before touching any code.

## Product

Neuroctivity is a static, bilingual (`ru` / `en`) neuroscience learning site for secondary-school
students and lifelong learners: a course page, a searchable workbook with quizzes and private
local notes, and an interactive 3D brain atlas. Planned additions: visitor reviews moderated
through Telegram, translated on approval, and a privacy-preserving visit counter.

The site is being moved from four hand-written HTML pages to a Next.js app. Until that conversion
is done (BRA-3, BRA-4), the legacy pages are served unchanged from `public/`.

## Locked architectural decisions

Do not revisit these without an explicit instruction from the user.

| Decision      | Choice                                                                                               | Consequence                                                                                                         |
| ------------- | ---------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Hosting       | Vercel Hobby                                                                                         | Usage limits: **no per-request SSR.** Every page is statically generated; the root layout sets `dynamic = 'error'`. |
| Frontend      | Next.js App Router, static                                                                           | Default `next build` output (not `output: 'export'`): rewrites and the Python functions need the Vercel runtime.    |
| Backend       | FastAPI in the root `api/` folder (Python Vercel Functions), same origin                             | No CORS, no second domain. One function, `api/index.py`; `next.config.ts` rewrites all of `/api/*` to it.           |
| API contract  | OpenAPI generated from the Pydantic models, committed as `.claude/backend/openapi.json`              | `make openapi` + `pnpm api:generate` after any API change; CI fails on drift. One error envelope for every error.   |
| API docs      | `/api/docs` only locally (`make run`), never on Vercel                                               | Swagger UI needs a CDN the CSP blocks; the CSP is not loosened. `/api/openapi.json` is served everywhere.           |
| Storage       | Upstash Redis is the single store                                                                    | No second database. Anything that needs persistence goes through a Redis port.                                      |
| Visit counter | HyperLogLog of a hash of IP + User-Agent + a daily salt                                              | The raw IP is never stored or logged. No cookies, ever.                                                             |
| Abuse control | Cloudflare Turnstile + rate limit on every write                                                     | A write without a verified Turnstile token is rejected before any other work.                                       |
| Moderation    | Telegram webhook                                                                                     | A review is `pending` until a moderator approves or rejects it; nothing unmoderated is shown.                       |
| Translation   | On approval only                                                                                     | One model call per approved review, never per view. Model output is untrusted input.                                |
| Review text   | Data, never instructions                                                                             | Rendered as plain text, never as HTML or Markdown, and never interpolated into a prompt as an instruction.          |
| Storage keys  | `conn_lang`, `neuroctivity-theme`, `neuroctivity-workbook-v1` stay as they are                       | Plain strings, no JSON wrapping, so existing visitors keep their language, theme and notes.                         |
| Atlas         | `public/mozg-3d-atlas-2.html` internals and the licence notices are untouched except as BRA-5 allows | Its SHA-256 is pinned in `src/shared/config`; a change must update the pin consciously.                             |
| Attribution   | FreeSurfer attribution and the `LICENSE-*.txt` links stay visible in the footer                      | A redesign that drops them is a licence violation, not a style choice.                                              |

## Stack

| Concern         | Tool                                                                        |
| --------------- | --------------------------------------------------------------------------- |
| Package manager | pnpm (version pinned in `package.json` → `packageManager`)                  |
| Framework       | Next.js App Router, React, Server Components by default                     |
| Language        | TypeScript, `strict: true`. Never JavaScript.                               |
| Styling         | Tailwind CSS v4 (tokens arrive with BRA-3)                                  |
| Server state    | TanStack Query (arrives with BRA-9)                                         |
| Client state    | Zustand (arrives with BRA-3)                                                |
| i18n            | chosen in BRA-3; `ru` + `en`                                                |
| Tests           | Vitest                                                                      |
| Backend         | Python 3.12, FastAPI, uv (locked), ruff, mypy strict, import-linter, pytest |

## Repository layout

```
.
├── CLAUDE.md
├── .claude/
│   ├── docs/              Frontend guides (FSD, code style, state, i18n)
│   ├── backend/           Backend engineering + testing guides, API contract
│   └── skills/            Repo skills (edge-case-bug-hunting)
├── app/                   Next.js route files only (thin re-exports)
├── src/                   Feature-Sliced Design: app, screens, widgets, features, entities, shared
├── public/                Published as-is at the site root (exactly seven files)
├── api/                   One Python Vercel Function: `api/index.py`, `app = create_app()`
├── backend/
│   ├── src/neuroctivity/  domain / application / infrastructure / transport, main.py
│   └── tests/
├── pyproject.toml, uv.lock, .python-version, Makefile   Python project (repo root, see below)
└── next.config.ts, eslint.config.ts, tsconfig.json, vitest.config.ts
```

The Python project files sit at the repo root on purpose: Vercel's Python builder looks for
`pyproject.toml` and `uv.lock` by walking up from the entrypoint in `api/` to the repo root, then
runs `uv sync --frozen --no-dev --no-editable`, which installs `neuroctivity` and its locked
dependencies into the function. A `pyproject.toml` inside `backend/` would not be found.

## Public surface

`public/` holds exactly the seven legacy files; anything else in the repository is a 404. The
short URLs Netlify used to serve (`/index`, `/workbook`, `/kira`, `/mozg-3d-atlas-2`) and `/` are
Next.js rewrites defined once in `src/shared/config/routes.ts`, next to the `/api/*` rewrite to the
Python function and the dev-only proxy to `make run`. Security headers and cache rules
are set by `headers()` in `next.config.ts`; every new file in `public/` needs a cache policy (see
the security headers guide).

## Running

```bash
pnpm install          # also installs the git hooks
pnpm dev              # http://localhost:3000
pnpm build && pnpm start
pnpm run ci           # typecheck + lint + format check + tests

make install          # Python 3.12 via uv
make check test coverage-gate
make run              # FastAPI on http://127.0.0.1:8000/api/health, docs at /api/docs
make openapi          # regenerate .claude/backend/openapi.json after an API change
pnpm api:generate     # regenerate src/shared/api/generated from it
```

`pnpm dev` proxies `/api/*` to `make run`, so run both when the site calls the API.

## Detailed guides

Read the guide that covers the area you are about to change. They are normative, not
suggestions.

- [`.claude/docs/architecture-fsd.md`](.claude/docs/architecture-fsd.md) — layers, slices,
  segments, the Next.js `app/` collision, import rules, where a new file belongs
- [`.claude/docs/code-style.md`](.claude/docs/code-style.md) — TypeScript, React, Server
  Components, naming, styling, static rendering
- [`.claude/docs/state-management.md`](.claude/docs/state-management.md) — TanStack Query vs
  Zustand vs localStorage, hydration, theme flash
- [`.claude/docs/i18n.md`](.claude/docs/i18n.md) — locales, keys, plurals, formatting
- [`.claude/docs/security-headers.md`](.claude/docs/security-headers.md) — CSP, HSTS,
  Permissions-Policy, cache rules, adding a file to `public/`
- [`.claude/backend/engineering-guide.md`](.claude/backend/engineering-guide.md) — ports and
  adapters, SOLID, boundaries, privacy, moderation, CI gate
- [`.claude/backend/testing.md`](.claude/backend/testing.md) — what to test, boundary checklist,
  untrusted model output
- [`.claude/backend/api-contract.md`](.claude/backend/api-contract.md) — endpoints (planned)
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — branches, commits, PRs, Jira, hooks, CI

## Hard rules

These override any default behaviour.

1. **No comments in source code.** The code and its names carry the meaning. Markdown docs are
   the place for explanation. The legacy HTML in `public/` is exempt: it stays byte-identical.
   So is the generated `src/shared/api/generated/` (written by `pnpm api:generate`, never by
   hand, excluded from lint and format).
2. **TypeScript only.** No `.js`, `.jsx`, `.mjs` or `.cjs` files outside `public/`. A config file
   that a tool can only read as JavaScript is the one exception, and it must be listed in
   `CONTRIBUTING.md` → "What CI checks". Today there is none.
3. **No `any`.** No non-null assertions (`!`). No `as` casts except immediately after a Zod parse
   at a system boundary, and `as const`.
4. **No magic strings.** Routes, published file names, storage keys, query keys and locale codes
   come from `src/shared/config`. If you are about to type a string literal that appears in more
   than one place, add it there instead.
5. **No user-facing string literals outside locale files.** The i18n library is chosen in BRA-3;
   the rule applies now. Every key is added to `ru` and `en` together.
6. **FSD import direction is enforced.** A layer may only import from strictly lower layers,
   always through a slice's or segment's public `index.ts`. ESLint fails the build otherwise.
7. **Nothing makes a route dynamic.** No `cookies()`, `headers()`, `searchParams` reads at request
   time, `no-store` fetches or `revalidate = 0`. The build fails if you try.
8. **Smallest possible change.** Do not refactor unrelated code, rename files, or introduce a new
   pattern when an existing one fits.
9. **No new dependencies** without asking. Search the repo for an existing utility before writing
   a new one.
10. **Never run git commands that write.** No commits, pushes, branches or PRs, and no
    `git add`, `git mv` or `git rm`: use plain `mv` and `rm`, rename detection works at commit
    time.

## Workflow expectations

Before implementing, estimate the size:

- **Small** (1–2 files, no architectural impact) — just do it.
- **Medium** (3–10 files) — present the plan first.
- **Large** (10+ files, or any change to architecture, state management, a public URL or a public
  contract) — present current state, proposed solution, affected files and risks, then wait for
  approval.

After implementing, verify: `pnpm run ci` is green (it includes `pnpm api:check`), `pnpm build` shows every route as static
(`○`), `make check test coverage-gate` is green when Python changed, no duplicated logic, and no
unrelated files were modified. Anything that can only be verified on Vercel is reported as
unverified, never claimed.

When the change adds or alters real behaviour — a rewrite, an endpoint, a validation rule, the
review state machine, a store action, a form, a parser, anything with branches — run the
[`edge-case-bug-hunting`](.claude/skills/edge-case-bug-hunting/SKILL.md) skill against what you
just touched before treating the work as done. Derive the boundary and failure cases, not the
happy path, and either fix what it surfaces or report it. Skip it only for changes with no logic:
docs, formatting, renames, pure config.
