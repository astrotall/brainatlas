# Backend engineering guide

How the API in `backend/` is written. It prescribes structure, principles and practices; the
companion files in this folder are normative where they are more specific:

- [`api-contract.md`](api-contract.md) — the endpoints, shapes and error codes.
- [`testing.md`](testing.md) — what to test and what not to.

## The one thing to remember

The site is static. The API exists for a small set of jobs — accept and moderate visitor reviews,
translate approved ones, count unique visits — and runs as **Python Vercel Functions on the Hobby
plan**, next to the static site on the same origin. Upstash Redis is the only store.

Everything follows from that: functions are stateless and short-lived, every request is cheap,
abuse is the main operational risk (a flood pauses the project), and visitor privacy is a hard
requirement, not a feature.

## Layout and deployment

```
api/index.py                       the one Vercel Function: app = create_app()
backend/src/neuroctivity/
  domain/                          pure rules: review, status machine, visitor hash
  application/                     use cases + ports (interfaces)
  infrastructure/                  adapters: Upstash, Turnstile, Telegram, model, clock
  transport/                       FastAPI routers, request/response models, error mapping
  config.py                        Settings (pydantic-settings, environment only)
  main.py                          composition root: create_app()
  openapi_export.py                make openapi / make openapi-check
backend/tests/
backend/vulture_whitelist.py       schema fields only Pydantic reads
pyproject.toml  uv.lock  .python-version  Makefile    repo root
```

- Every `.py` file in `api/` with a top-level `app` becomes its own Vercel Function. There is
  exactly one, `api/index.py`, and a Vitest guard (`api-rewrites.test.ts`) fails if another
  appears. Keep it to the two lines above.
- Vercel's Python builder finds `pyproject.toml` and `uv.lock` by walking up from `api/` to the
  repo root, then runs `uv sync --frozen --no-dev --no-editable`: the `neuroctivity` package and
  its locked runtime dependencies are installed into the function. Dev dependencies never ship.

### Routing `/api/*` to one app (BRA-6)

Under the Next.js preset, Vercel builds `api/*.py` files as separate functions and routes only
their exact paths; any other `/api/*` path would get Next's HTML 404. So:

1. `next.config.ts` rewrites `/api` and `/api/:__api_path*` to `/api/index?__path=:__api_path*`
   (defined once in `src/shared/config/routes.ts` as `API_REWRITES`).
2. `RestoreForwardedPath` (transport) removes **both reserved parameters**, `__path` and
   `__api_path`, from the query. Only when the app sees `/api/index` or `/api/index.py` does it
   rebuild the original path, from the **first** `__path`. If Vercel hands the function the
   original path instead, the parameters are just dropped. Either way FastAPI routes the real
   path, so 404 and 405 come from FastAPI in the error envelope.

On Vercel a rewrite also appends each named source parameter to the destination query, even one
the destination already uses (see `api-contract.md` → "Routing"). That is why the source parameter
has a reserved name the middleware strips, instead of an ordinary one like `path` that the app
would reject as unknown.

The path the function sees after a rewrite is not documented by Vercel; the middleware works for
both cases, and the preview curls in the BRA-6 report check it. If the Next rewrite does not reach
the function on Vercel, the fallback is a `vercel.json` with the same two rewrites (destination
`/api/index?__path=$1`, which names no source parameter, so nothing extra is appended). It is not added unless needed, because Vercel recommends framework-native
rewrites for Next.js.

Rejected: one file per path (unknown paths become Next's HTML 404, every file cold-starts
separately) and Vercel Services (Beta, needs a preset change and `vercel.json`).

## Guiding principles

1. **The contract is the boundary.** The Pydantic models are the contract and generate the
   OpenAPI schema. Validate every request against them on the way in and every response on the way
   out.
2. **Fail loud internally, fail gracefully externally.** Internally: crash on programmer error,
   log with context. Externally: never leak a stack trace; always return the documented error
   envelope with a stable `code`.
3. **Smallest surface that satisfies the contract.** Do not add endpoints, fields, headers or
   config the contract does not require.
4. **Privacy by construction.** If a value would let someone identify a visitor, it is not stored.

## Architecture: ports and adapters

Dependencies point **inward only**. The inner layers know nothing about HTTP, Redis, Turnstile,
Telegram or the model provider.

```
        ┌───────────────────────────────────────────┐
        │  Transport (inbound adapters)              │   FastAPI routes, request models,
        │   ┌───────────────────────────────────┐    │   error envelope, status codes
        │   │  Application                       │    │   use cases: submit review,
        │   │   ┌───────────────────────────┐    │    │   moderate review, record visit
        │   │   │  Domain                    │    │    │   review, status machine,
        │   │   │  (pure business rules)     │    │    │   visitor hash, limits
        │   │   └───────────────────────────┘    │    │
        │   └───────────────────────────────────┘    │
        │  Infrastructure (outbound adapters)         │   Upstash, Turnstile, Telegram,
        └───────────────────────────────────────────┘   model, clock
```

- **Domain** — the review and its invariants (rating range, text limits, no links), the status
  machine, the visitor-hash rule. Pure: no I/O, no clock reads, no randomness pulled in directly —
  those are passed in. import-linter enforces it.
- **Application** — orchestrates a use case by calling _ports_ (interfaces it defines): a
  `ReviewStore`, a `HumanCheck` (Turnstile), a `ReplayGuard`, a `RateLimiter`, a
  `ModerationNotifier`, and later a `Translator` and a `VisitCounter` (`application/ports.py`). It
  does not know which provider implements them. The clock and the id factory are ports too.
- **Infrastructure** — the adapters that implement the ports. Swappable without touching the
  core.
- **Transport** — maps HTTP to use-case calls and back. Owns request validation, the error
  envelope and status codes.
- **`main.py` + `wiring.py`** — the composition root. `wiring.py` builds the adapters from
  `Settings` and the use cases from the adapters; `main.py` puts them on `app.state`; route
  handlers read them back through dependencies. Tests pass their own `ReviewEndpoints` to
  `create_app` instead.

## SOLID, applied to this service

- **S** — validating a review, verifying Turnstile, limiting the rate, storing, notifying the
  moderator and translating are separate units. The thing that talks HTTP is not the thing that
  calls Redis is not the thing that calls the model.
- **O** — a new language or a new moderation action extends a registry or a table; it does not
  edit a switch every path flows through.
- **L** — a fake adapter used in tests honours the same contract as the real one: same error
  types, same timeout semantics, same output shape.
- **I** — ports are shaped by what the application needs. The translator needs "translate this
  text into that language", not a ten-method LLM client.
- **D** — use cases receive their ports. Never construct a Redis client or a model client inside
  domain or application code.

## Boundaries and validation

The system boundary is where trust changes. Validate hard there, trust freely inside.

- **Inbound:** every body, query parameter and header is validated before any work starts.
  Unknown fields are rejected. Text is trimmed before length checks. Bad input →
  `422 validation`, never a 500.
- **Turnstile first:** a write without a verified token is rejected before it touches Redis or
  the rate limiter's budget for valid requests.
- **Outbound to the client:** the response model is the contract; a pending or rejected review
  can never be serialised into the public list.
- **Provider output is untrusted:** Turnstile, Telegram and especially the model can return
  malformed, unexpected or hostile data. Parse it into domain types at the adapter; never pass raw
  provider output through.
- Keep SDK types out of the domain. Map them at the adapter.

## Review text is data, never instructions

- A review is stored and returned exactly as the visitor wrote it (after trimming). It is
  rendered as plain text by the site — never as HTML or Markdown.
- When a review is translated, its text goes to the model as **delimited content to translate**,
  never concatenated into the instructions. The system prompt says the content may contain
  instructions and that they must be translated, not followed.
- The translation is validated like any other untrusted input (language, length bounds, no added
  links or markup, not a chat reply) before it is stored. A translation that fails validation is
  dropped; the review is still published in its original language.

## The review lifecycle: a state machine

```
           approve
 pending ───────────▶ approved
    │
    └───────────────▶ rejected
           reject
```

- `pending` is the only initial state, and the only state with outgoing transitions. Every other
  transition is refused with a domain error.
- Moderation arrives through the Telegram webhook (BRA-7). The webhook verifies its secret, and
  the same update delivered twice changes state once.
- Translation runs **on approval only**, once per review — never per view.
- Only `approved` reviews are readable through the public API.

## Rate limiting and abuse

- Every write (`POST /api/reviews`, `POST /api/visit`) is rate-limited. Over the limit →
  `429 rate_limited` with `Retry-After`.
- The limit key is `HMAC-SHA256(CLIENT_HASH_SECRET, address group)` (`domain/client.py`), never
  the raw IP. The address is the last value of `x-vercel-forwarded-for`; see
  [`api-contract.md`](api-contract.md) → "Rate limits".
- Turnstile runs before the limiter, so only a visitor who passed the human check spends budget,
  and each token is claimed once in Redis because Cloudflare's own reuse check is eventually
  consistent.
- Limits, windows and TTLs are configuration values, not literals.
- Prefer failing closed: if the rate limiter or Turnstile cannot answer, the write is refused.

## Privacy

- **No raw IP address is ever stored or logged.** The visit counter feeds a HyperLogLog with a
  hash of IP + User-Agent + a daily salt; rate-limit keys use a hash as well.
- The daily salt rotates and old salts are not kept, so yesterday's hashes cannot be recomputed.
- No cookies, no fingerprinting beyond the hash above, no third-party analytics.
- Logs never contain a Turnstile token, a secret, a raw IP or a full review text.

## Error handling

- One error envelope for every response that is not a success, including Starlette's own 404 and
  405, validation, an oversized body and an unhandled exception:
  `{"error": {"code", "message", "fields"?: [{"field", "message", "reason"}]}}`. The codes and
  reasons are the enums `ErrorCode` and `FieldReason` in `transport/errors.py`; their list is in
  [`api-contract.md`](api-contract.md). Do not invent one outside it.
- The client maps `code` and `reason` to translated messages and never renders `message`.
- Conversion happens in one place: `transport/error_handlers.py` (typed errors, validation,
  Starlette HTTP errors) and `ContainUnhandledErrors` in `transport/middleware.py` (anything
  else). Domain and application code raise typed errors; the mapper picks the status and code.
- Never leak internal detail. A validation error never echoes the submitted value. An unhandled
  error is logged as `unhandled_error` with the exception **type** and the traceback, never its
  message, which may contain review text or a provider response.
- Every route declares its error statuses with `error_responses(...)`, so they are in the schema
  and the contract tests can check them.

### Middleware order

Outermost first: `ApplyResponseDefaults` (`Cache-Control: no-store` unless the route set one,
`X-Content-Type-Options: nosniff`) → `AnswerHeadAsGet` → `ContainUnhandledErrors` →
`RestoreForwardedPath` → `LimitBodySize` (16 KiB, rejects before parsing). HEAD runs the GET route
and drops the body, so headers and status are identical.

## Resilience

- **Timeouts on every outbound call** (Upstash, Turnstile, Telegram, the model). A function that
  hangs burns the Hobby budget.
- Retries only for transient failures, with backoff, and only where the call is idempotent.
- The model is the slowest dependency; a translation failure never blocks an approval.

## Configuration and secrets

- All configuration from environment variables through `neuroctivity.config.Settings`
  (pydantic-settings). Vercel project settings in production; locally the shell or `make run`.
  `.env.example` lists every name with no value.
- Secrets never in source, never in logs, never in error responses.
- A **malformed** value (for example `API_DOCS_ENABLED=banana`) fails at startup. A **missing**
  provider secret does not stop the app: health and `/api/openapi.json` keep working, and the
  endpoints that need it answer `503 service_unavailable` and log the missing variable names
  (BRA-6 decision).
- `/api/docs` is served only when `API_DOCS_ENABLED=true` and `VERCEL` is unset. Swagger UI loads
  from a CDN the CSP blocks, and the CSP is not loosened for it.

### Environment variables

Names only; `.env.example` lists them, values live in Vercel.

| Variable                                                                       | Required for          | Notes                                                                                                                |
| ------------------------------------------------------------------------------ | --------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`                           | both review endpoints | from the Upstash database page                                                                                       |
| `REDIS_KEY_PREFIX`                                                             | both review endpoints | `[a-z0-9][a-z0-9:_-]{0,39}`; e.g. `prod`, `preview`: one free database, separate data                                |
| `TURNSTILE_SECRET_KEY`                                                         | `POST`                | a Cloudflare test secret is refused when `VERCEL_ENV=production`                                                     |
| `TURNSTILE_HOSTNAMES`                                                          | optional              | comma list; when set, the token's hostname must be listed. Leave it empty with test keys (they answer `example.com`) |
| `TURNSTILE_REPLAY_GUARD`                                                       | optional, default on  | `false` only for previews on test keys; refused in production                                                        |
| `CLIENT_HASH_SECRET`                                                           | `POST`                | at least 32 characters, random; rotating it resets every rate bucket                                                 |
| `REVIEW_LIMIT_PER_HOUR`, `REVIEW_LIMIT_PER_DAY`, `REVIEW_GLOBAL_LIMIT_PER_DAY` | optional              | defaults 3, 10, 200; each at least 1                                                                                 |
| `STORAGE_BACKEND`                                                              | optional              | `upstash` (default) or `memory`; `memory` is refused on Vercel                                                       |
| `CLIENT_IP_SOURCE`                                                             | optional              | `vercel` (default, `x-vercel-forwarded-for`) or `peer` (local only)                                                  |
| `API_DOCS_ENABLED`                                                             | local only            | never set on Vercel                                                                                                  |

`VERCEL` and `VERCEL_ENV` are read to refuse the unsafe combinations above; they require
"Automatically expose System Environment Variables" in the Vercel project; check that it is on,
or the production refusals cannot fire.

### Redis: client, keys and scripts

The official `upstash-redis` client over Upstash's REST API: one HTTPS request per call, no
connection pool to leak between invocations. Retries and telemetry are off and every call is cut
off after 2 s (`BoundedScriptRunner`; the client itself has no timeout). Only the listed
transport, decoding and Upstash errors become `503`; their text is never logged or returned, only
the exception type. A programming error is not disguised as an outage.

Every operation is **one Lua script** (`infrastructure/redis_scripts.py`), so it is atomic and
costs one command against the free tier's monthly budget:

| Key (after `REDIS_KEY_PREFIX:`)       | Type   | Content                                                                               |
| ------------------------------------- | ------ | ------------------------------------------------------------------------------------- |
| `review:{uuid}`                       | hash   | `rating`, `text`, `lang`, `status`, `created_at` (ms), `translation_ru`/`_en` (BRA-7) |
| `reviews:pending`, `reviews:approved` | zset   | review ids scored by `created_at`; BRA-7 moves an id from one to the other            |
| `rl:{hour,day}:{client}:{n}`          | string | per-client counter for window number `n`, TTL one window                              |
| `rl:global:global:{n}`                | string | all-clients daily counter                                                             |
| `turnstile:{sha256(token)}`           | string | single-use claim, TTL 300 s                                                           |

- `create_review` refuses to overwrite an existing id. `list_approved` reads the newest ids from
  the approved index and their hashes in one call.
- `acquire_windows` checks every window first and increments only if all have room, so a refused
  attempt changes nothing. After `INCR` it sets the TTL whenever the key has none, which also
  repairs a key left without one.
- Everything read back is untrusted: a record with a bad id, rating, language, status, length or
  timestamp is skipped and logged as `review_record_skipped`; an answer of the wrong shape is
  `503`.
- The in-memory adapters (`infrastructure/memory.py`) implement the same ports with the same
  semantics and run through the same contract tests; they serve `make run` and the unit tests.

- No magic numbers: timeouts, limits, TTLs and text bounds are named values.

## Statelessness

- Functions keep no state between requests. Everything that must survive lives in Redis.
- Any instance can serve any request; cold starts are normal.
- Keep imports light in the entrypoint: everything imported at module level is paid on every cold
  start.

## Testing

[`testing.md`](testing.md) is the full approach. The summary:

- **Domain:** pure unit tests — the state machine, the review invariants, the visitor hash.
- **Application:** against fake ports, including every failure mode and malformed provider
  output.
- **Transport:** every route's statuses and bodies, including every error code, checked against
  the generated schema.
- **Adapters:** a thin, separate integration suite against real providers, not in the fast suite.

## CI enforcement

The backend is gated by three jobs in `.github/workflows/ci.yml`: `backend`, `backend-audit` and
`secrets`. Every point runs through a `make` target at the repo root, so a failure reproduces
locally with the same command CI uses.

No linter verifies SOLID. What CI can enforce are the measurable proxies that make violations
expensive and visible; review still checks the principles themselves.

| #   | Point                | Enforced by                                                     | CI job / `make` target      |
| --- | -------------------- | --------------------------------------------------------------- | --------------------------- |
| 1   | Formatter            | `ruff format --check`                                           | `backend` / `check`         |
| 2   | Linter               | `ruff check` with `select = ["ALL"]`, any finding fails         | `backend` / `check`         |
| 3   | Types                | `mypy` strict plus `disallow_any_explicit`; suppression guard   | `backend` / `check`         |
| 4   | Layering             | import-linter, three contracts in `pyproject.toml`              | `backend` / `check`         |
| 4a  | Contract drift       | `openapi_export --check` against `.claude/backend/openapi.json` | `backend` / `check`         |
| 5   | Complexity budget    | ruff `C901`, `PLR0913`, `PLR0915`, `PLR1702`                    | `backend` / `check`         |
| 6   | Dead code            | `vulture` over `backend/src`                                    | `backend` / `check`         |
| 7   | Tests                | pytest, including the transport tests                           | `backend` / `test`          |
| 8   | Coverage floors      | `coverage report --fail-under`                                  | `backend` / `coverage-gate` |
| 9   | Dependency + secrets | `pip-audit` over `uv.lock`; `gitleaks` over the full history    | `backend-audit`, `secrets`  |

1. **Formatter check** — no debate about style in review.
2. **Linter, warnings are errors** — every ruff finding fails the build. The only rule families
   switched off are `D` (docstrings: the repo carries no comments), `CPY` (copyright headers) and
   the two that conflict with the formatter (`COM812`, `ISC001`). Tests additionally allow
   `assert` and magic values; `api/*.py` allows `INP001`, because an `__init__.py` in `api/` would
   itself become a function.
3. **Static types** — mypy `strict`, `disallow_any_explicit`, `disallow_any_unimported`, with the
   pydantic plugin. `make guard` fails on any `# type: ignore`, `# mypy: ignore-errors`, `# noqa`,
   `# ruff: noqa` or `# pragma: no cover` under `backend/src`, `backend/tests` and `api`: the repo
   allows no comments, so a justification for a suppression cannot exist.
4. **Layering** — three import-linter contracts: the layer order (`openapi_export` → `main` →
   `config` → `transport` | `infrastructure` → `application` → `domain`), domain and application
   free of HTTP and settings packages (`fastapi`, `starlette`, `uvicorn`, `httpx`, `httpx2`,
   `pydantic_settings`), and a pure domain (no clock,
   randomness, serialisation, schema or I/O modules). When the Redis, Telegram or model SDKs
   arrive, they are added to the forbidden lists in the same change.
5. **Complexity budget** — mirrors the frontend's (`eslint.config.ts`):

   | Limit                 | Frontend | Backend         | Rule      |
   | --------------------- | -------- | --------------- | --------- |
   | Cyclomatic complexity | 12       | 12              | `C901`    |
   | Parameters            | 4        | 4               | `PLR0913` |
   | Nesting depth         | 4        | 4 nested blocks | `PLR1702` |
   | Function size         | 80 lines | 40 statements   | `PLR0915` |

   Function size is counted in statements on the backend because a line count would reward or
   punish formatter wrapping. `PLR1702` is a preview rule, enabled explicitly with
   `explicit-preview-rules`.

6. **Dead code** — `F401`, `F811`, `F841` (via `ALL`) and `vulture` at 60% confidence over
   `backend/src`. Framework wiring is listed in `[tool.vulture]` rather than hidden: route
   handlers (`@router.*`), `model_config` and the `create_app` factory. `ignore_names` is global,
   so a new name goes there only when a framework calls it by name and it cannot be made visible
   by passing it through a constant. Schema fields and enum members that only Pydantic reads are
   named one by one in `backend/vulture_whitelist.py`; a new model field is added there.
7. **Tests** — `make test` runs the whole suite with branch coverage.
8. **Coverage floors** — `make coverage-gate`:

   | Scope                                    | Floor |
   | ---------------------------------------- | ----- |
   | Whole package                            | 95%   |
   | `domain` + `application`                 | 98%   |
   | `infrastructure`, `transport`, `main.py` | 90%   |

   Coverage is a floor, not a goal; do not chase 100%.

9. **Security** — `make audit` exports `uv.lock` with hashes and runs `pip-audit` (version pinned
   in the Makefile). The `secrets` job runs `gitleaks` (version and sha256 pinned in the workflow)
   over the full history with `.gitleaks.toml`, which extends the default rules with no allowlist.

### What stays in review, not CI

- Does each unit have one reason to change, or is a "god service" forming? (S)
- Does a new language or moderation action extend a registry, or edit a shared switch? (O)
- Do fakes and real adapters honour the same contract — same errors, same timeouts? (L)
- Are ports shaped by what the application needs, not by the provider SDK? (I)
- Is anything constructing a client or opening a connection inside domain or application code? (D)
- Could anything here store or log a raw IP, a token or a secret?
