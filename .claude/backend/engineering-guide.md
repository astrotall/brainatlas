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
api/health.py                      thin Vercel entrypoint: app = create_app()
backend/src/neuroctivity/
  domain/                          pure rules: review, status machine, visitor hash
  application/                     use cases + ports (interfaces)
  infrastructure/                  adapters: Upstash, Turnstile, Telegram, model, clock
  transport/                       FastAPI routers, request/response models, error mapping
  main.py                          composition root: create_app()
backend/tests/
pyproject.toml  uv.lock  .python-version  Makefile    repo root
```

- Every `.py` file in `api/` becomes its own Vercel Function at the matching path
  (`api/health.py` → `/api/health`) and must define a top-level `app`. Keep them to the two lines
  above; nothing else goes in `api/`, because any other `.py` file there would also become a
  function.
- Vercel's Python builder finds `pyproject.toml` and `uv.lock` by walking up from `api/` to the
  repo root, then runs `uv sync --frozen --no-dev --no-editable`: the `neuroctivity` package and
  its locked runtime dependencies are installed into the function. Dev dependencies never ship.
- How the whole `/api` prefix is routed to one app (needed for `/api/docs` and
  `/api/openapi.json` on Vercel) is decided in BRA-6.

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
  `ReviewStore`, a `HumanCheck` (Turnstile), a `RateLimiter`, a `Translator`, a `Moderator`
  notifier, a `VisitCounter`. It does not know which provider implements them.
- **Infrastructure** — the adapters that implement the ports. Swappable without touching the
  core.
- **Transport** — maps HTTP to use-case calls and back. Owns request validation, the error
  envelope and status codes.
- **`main.py`** — the composition root. It builds the adapters from configuration and wires them
  into the use cases on `app.state`; route handlers read them back through dependencies.

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
  `429 rate_limited`.
- The limit key is a hash of the client, never the raw IP.
- Limits, windows and TTLs are configuration values, not literals.
- Prefer failing closed: if the rate limiter or Turnstile cannot answer, the write is refused.

## Privacy

- **No raw IP address is ever stored or logged.** The visit counter feeds a HyperLogLog with a
  hash of IP + User-Agent + a daily salt; rate-limit keys use a hash as well.
- The daily salt rotates and old salts are not kept, so yesterday's hashes cannot be recomputed.
- No cookies, no fingerprinting beyond the hash above, no third-party analytics.
- Logs never contain a Turnstile token, a secret, a raw IP or a full review text.

## Error handling

- One error envelope for every endpoint: `{"error": {"code": "...", "message": "..."}}` with the
  stable codes in [`api-contract.md`](api-contract.md). Do not invent codes outside it.
- The client maps `code` to a translated message and never renders `message`.
- Convert exceptions to the envelope in exactly one place (a transport-layer error mapper).
  Domain and application code raise typed errors; the mapper picks the status and code.
- Never leak internal detail (stack traces, provider error text) to the client. Log it, return
  `internal`.

## Resilience

- **Timeouts on every outbound call** (Upstash, Turnstile, Telegram, the model). A function that
  hangs burns the Hobby budget.
- Retries only for transient failures, with backoff, and only where the call is idempotent.
- The model is the slowest dependency; a translation failure never blocks an approval.

## Configuration and secrets

- All configuration from environment variables (Vercel project settings in production, a local
  `.env` that is never committed; `.env.example` lists the names when the first one exists).
- Secrets never in source, never in logs, never in error responses.
- Fail fast at startup if required configuration is missing.
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

| #   | Point                | Enforced by                                                   | CI job / `make` target      |
| --- | -------------------- | ------------------------------------------------------------- | --------------------------- |
| 1   | Formatter            | `ruff format --check`                                         | `backend` / `check`         |
| 2   | Linter               | `ruff check` with `select = ["ALL"]`, any finding fails       | `backend` / `check`         |
| 3   | Types                | `mypy` strict plus `disallow_any_explicit`; suppression guard | `backend` / `check`         |
| 4   | Layering             | import-linter, three contracts in `pyproject.toml`            | `backend` / `check`         |
| 5   | Complexity budget    | ruff `C901`, `PLR0913`, `PLR0915`, `PLR1702`                  | `backend` / `check`         |
| 6   | Dead code            | `vulture` over `backend/src`                                  | `backend` / `check`         |
| 7   | Tests                | pytest, including the transport tests                         | `backend` / `test`          |
| 8   | Coverage floors      | `coverage report --fail-under`                                | `backend` / `coverage-gate` |
| 9   | Dependency + secrets | `pip-audit` over `uv.lock`; `gitleaks` over the full history  | `backend-audit`, `secrets`  |

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
4. **Layering** — three import-linter contracts: the layer order (`main` → `transport` |
   `infrastructure` → `application` → `domain`), domain and application free of HTTP packages
   (`fastapi`, `starlette`, `uvicorn`, `httpx`, `httpx2`), and a pure domain (no clock,
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
   by passing it through a constant.
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
