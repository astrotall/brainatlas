# Working in this repository

Branches, commits and pull requests. The rules are the same for the site and the API.

## Branches

`main` is protected and always releasable: never push to it directly; every change goes through
a pull request with green CI. Everything else is a short-lived branch off `main`.

```
<type>/BRA-<number>/<short-dashed-description>
```

The type is the same as the commit type (below). The Jira key is uppercase, exactly as in Jira.
The description is latin, lowercase, 2–5 words that name the task.

```
chore/BRA-1/nextjs-scaffold
feat/BRA-6/reviews-endpoint
fix/BRA-12/workbook-theme-flash
docs/BRA-14/backend-testing-guide
```

The key is mandatory: Jira uses it to attach the branch, its commits and the pull request to the
task and to move its status. A branch with no key never shows up on the task.

A branch with no Jira task is only for trivia that never enters the tracker (`ci/fix-pnpm-cache`).
Anything a visitor sees has a task.

A branch lives until it merges and is deleted right after. There is no long-lived `develop`
branch.

## Commits — Conventional Commits

```
<type>(<scope>): <description>

[body — why, if not obvious]

BRA-<number>
```

The subject is short (up to ~72 characters), **in English**, imperative mood, no trailing period.
Branch names, PR titles and documentation are English as well.

The Jira key goes on its own line in the footer, after a blank line, in uppercase. Keep it out of
the subject: the subject is read by people, the footer by Jira.

```
chore(infra): scaffold the Next.js app and serve the legacy pages from public

BRA-1
```

```
feat(reviews): accept a review behind Turnstile and a rate limit
fix(atlas): keep the embed camera still on resize
refactor(web): move the theme toggle into shared/ui
docs(api): describe the moderation state machine
chore(deps): bump next to 16.4.x
ci: cache the uv download
```

### Types

| Type       | When                                                      |
| ---------- | --------------------------------------------------------- |
| `feat`     | new user-facing functionality                             |
| `fix`      | a bug fix                                                 |
| `refactor` | a code change that does not alter behaviour               |
| `perf`     | a performance improvement                                 |
| `style`    | formatting that does not change meaning                   |
| `docs`     | documentation, including `.claude/`                       |
| `test`     | tests                                                     |
| `build`    | build, dependencies                                       |
| `ci`       | pipelines                                                 |
| `chore`    | anything else that does not belong in the product history |
| `revert`   | reverting a commit                                        |

### Scopes

`web`, `ui`, `atlas`, `api`, `reviews`, `stats`, `i18n`, `deps`, `ci`, `docs`, `infra`.

The scope is optional when a change is not tied to one place.

### Breaking changes

A `!` after the scope plus a footer:

```
feat(api)!: rename the review status field

BREAKING CHANGE: the site and the API must update together.

BRA-6
```

## Jira (project BRA)

The key is `BRA-<number>`, always uppercase: `BRA-6`, not `bra-6` or `Bra6`. Jira does not
recognise a lowercase key and the link silently fails.

Three places must carry it, each giving a different link:

| Where                                 | Why                                                       |
| ------------------------------------- | --------------------------------------------------------- |
| Branch name                           | Jira shows the branch on the task and offers to open a PR |
| Commit footer                         | commits appear in the task's development panel            |
| PR title — at the end, in parentheses | the PR attaches to the task and moves its status          |

You move the status yourself:

| When                                   | Status                                      |
| -------------------------------------- | ------------------------------------------- |
| Picked it up, opened a branch          | **In Progress**                             |
| Opened a pull request                  | **In Review**                               |
| PR merged into `main`                  | **Done**                                    |
| Waiting on a reply, another PR, access | **Blocked**, with a comment saying what for |

One task — one branch — one PR. If a task grows, split it into sub-tasks in Jira rather than
dragging unrelated changes into one branch. If a PR closes several tasks, list every key on its
own footer line, and comma-separate them in the PR title: `(BRA-6, BRA-7)`.

## What must ship in one commit

Some files drift apart silently. Change them together:

- **Any endpoint, request or response field, status code or error code** → the FastAPI models
  and routes (the OpenAPI schema is generated from them) **and**
  [`.claude/backend/api-contract.md`](.claude/backend/api-contract.md), in the same change.
- **A route, published file or storage key** → `src/shared/config` and its tests. A URL that was
  public stays served.
- **An i18n key** → both `ru` and `en`. A key that exists in only one locale is a bug.
- **A change to the atlas** (BRA-5 only) → the file and its pinned `ATLAS_SHA256`.
- **A decision on an open question** → recorded under `.claude/`, not just in chat.

## Pull requests

Run the gate locally before pushing — CI runs the same commands:

```bash
pnpm run ci                    # typecheck + lint (FSD boundaries + strict rules) + format check + tests
pnpm build                     # every route must be static (○)
make check test coverage-gate  # when anything Python changed
```

`pnpm format` and `make fix` fix anything auto-fixable.

The PR title is the commit subject plus the Jira key at the end:
`chore(infra): scaffold the Next.js app and serve the legacy pages from public (BRA-1)`.

The body has three sections and a link:

```
## Summary
What changes and why. A before/after screenshot if the UI changed.

## Verified
What you checked by hand, and what could not be verified locally (anything Vercel-only).

## Checks
pnpm run ci, pnpm build, make check test coverage-gate — with their results.

Closes https://astrotall.atlassian.net/browse/BRA-<n>
```

One PR — one task. Refactoring nearby code "while you are here" goes in a separate PR.

## Git hooks (Husky)

`pnpm install` runs the `prepare` script, which points git's `core.hooksPath` at `.husky/`.
Nothing else is needed from a fresh clone.

**What `pre-commit` runs.**

- Always: `pnpm run ci` — typecheck, lint, format check, tests.
- Only when the staged files touch `api/`, `backend/`, `pyproject.toml`, `uv.lock`,
  `.python-version` or `Makefile`: `make check test coverage-gate`. A frontend developer without
  Python installed is not blocked by the backend gate.

If either is red, the commit is blocked.

**Bypass.** `git commit --no-verify` (`-n`) skips the hook. CI still runs the same gate on the PR,
so a bypass only defers the failure.

## What CI checks

Defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml). Each job name is a required
status check on `main`:

- **Frontend (strict)** — a "no JavaScript in source" guard (any tracked `*.js`, `*.jsx`, `*.mjs`
  or `*.cjs` outside `public/` fails; there are no exceptions today), `tsc`, ESLint (FSD layer
  boundaries, strict TypeScript and complexity limits, `--max-warnings 0`), a Prettier check, the
  Vitest suite (public surface, legacy URLs, atlas checksum, storage keys) and `next build`, which
  fails if any route becomes dynamic.
- **Backend** — `make check` (a guard that rejects `# type: ignore` / `# noqa` suppressions, Ruff
  format check, Ruff lint with the complexity budget, mypy strict, import-linter layering
  contracts, vulture dead-code scan), `make test` and `make coverage-gate` (coverage floors).
- **Backend dependency audit** — `make audit`, a pip-audit of the locked dependencies.
- **Secret scan** — gitleaks over the full git history, pinned by version and checksum,
  configured by `.gitleaks.toml`.

The reasoning and the exact numbers are in
[`.claude/backend/engineering-guide.md`](.claude/backend/engineering-guide.md) → "CI
enforcement".

A red CI is never merged.
