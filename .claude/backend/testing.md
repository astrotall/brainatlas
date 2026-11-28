# Backend testing guide

How to test the API in `backend/`. It prescribes _what_ to test and _what not to_; the runner is
pytest with coverage, run through `make test` and `make coverage-gate`.

## The one principle: test the boundaries, not the happy path

The happy path is the least likely place a bug hides and the most likely thing to be exercised by
hand anyway. A suite that is mostly happy-path assertions is green and useless.

So write **one** happy-path case per behaviour, as an anchor that documents intent, and spend the
rest of the budget where bugs actually live:

- **boundaries** — min, max, one below min, one above max, empty, zero, off-by-one;
- **failure modes** — what Redis, Turnstile, Telegram, the model and the network do _wrong_;
- **invariants** — the things that must never be true, regardless of input;
- **state transitions** — the illegal ones, not just the legal ones;
- **idempotency and concurrency** — the same request twice, the same webhook update twice.

If a test would still pass when you delete a random branch of the code, it is testing the happy
path. Delete it or point it at a boundary.

## What each layer tests

Mirrors the layers in [`engineering-guide.md`](engineering-guide.md). Dependencies point inward,
so tests get cheaper and more valuable the further in you go.

| Layer           | Kind                    | Runs               | Focus                                                                              |
| --------------- | ----------------------- | ------------------ | ---------------------------------------------------------------------------------- |
| **Domain**      | Pure unit, no I/O       | Every commit, ms   | Review invariants, the status state machine, the visitor-hash rules.               |
| **Application** | Unit against fake ports | Every commit       | Orchestration under success **and** every failure mode. No network.                |
| **Adapters**    | Integration             | Separately, rarely | The seam with real Upstash, Turnstile, Telegram, the model. Not in the fast suite. |
| **Transport**   | Contract tests          | Every commit       | Every status and body matches the committed `openapi.json`; every error code.      |

Contract tests read `.claude/backend/openapi.json` through `backend/tests/transport/openapi.py`:
`assert_documented` checks that a response's status is declared for the operation and that its
body validates against the declared schema; `assert_error` checks the envelope, `no-store` and
`nosniff`; `field_reasons` returns the `(field, reason)` pairs of a `422`. Assert on `code` and
`reason`, never on `message`. A test that freezes the schema itself checks the published limits
(`minimum`, `maxLength`, `enum`), because the frontend reads them from there.

The bulk of the suite is domain + application. Adapters get a thin integration layer, not
exhaustive coverage — you are not testing the provider's SDK.

## The boundaries that matter for this API

This is the checklist. These are the cases worth writing; the happy path is assumed.

### Request validation (reviews)

- `rating` at 0 (reject), 1 (accept), 5 (accept), 6 (reject), `"5"` as a string, `5.0`, `5.5`,
  `true`, `1e400`, `NaN`.
- Text at the minimum length − 1, the minimum, the maximum, the maximum + 1 — after
  normalization, counted in code points (an astral emoji is one). Whitespace-only text is empty.
- A link in the text (`http://`, `https://`, `www.`, a bare domain) is rejected.
- `lang` outside `ru` / `en` is rejected.
- Unknown or extra fields are rejected; so is an unknown or repeated query parameter.
- A body over 16 KiB, a body that is not JSON, a non-JSON content type and an absent body each
  yield `422 validation_failed` with a `body` field, never a 500.
- No validation error echoes the submitted value.
- Bad input yields `422 validation_failed` in the documented error envelope, never a 500.

### Routing and the envelope

- Any unknown `/api` path, a wrong method (with the exact `Allow`), `HEAD` on every `GET`, and an
  unhandled exception all answer the envelope.
- The forwarded path: `/api/index?__path=…` routes as the original path with the original query;
  a `__path` reaching any other path is dropped; a forwarded path with no route is `404`.
- The local proxy exists only for `next dev` with `NODE_ENV=development`; every other phase and
  `NODE_ENV` pair yields the deployed rewrites and identical headers (`api-rewrites.test.ts`).

### Abuse controls

- A missing, empty, expired or reused Turnstile token → `403 turnstile_failed`, and no review is
  stored.
- Turnstile verification itself times out → the request fails closed, it does not pass.
- Over the limit → `429 rate_limited`. The limit is keyed by the hashed client, and two clients
  never share a bucket.

### Review lifecycle — the state machine

- `pending → approved` and `pending → rejected` are the only transitions. Approving a rejected
  review, rejecting an approved one, or approving twice is refused.
- A `pending` or `rejected` review never appears in `GET /api/reviews`, in any language.
- The same Telegram update delivered twice changes state once.
- A webhook call without the configured secret is rejected and changes nothing.

### Translation — the untrusted model-output suite

The translation runs once, on approval, and its output is **untrusted input**:

- Empty output, output in the wrong language, or output that is the original text unchanged →
  the review is published without a translation (`translated: false` for the other locale), not
  with garbage.
- Output far longer than the original (a model that "continues" the text) is rejected.
- Output that contains instructions, markup, links or a reply to the reviewer ("Sure, here is the
  translation:") is rejected or cleaned, never published as is.
- A review whose text is a prompt-injection payload ("Ignore previous instructions and …") is
  translated as text; the system prompt is never affected, and the output is checked like any
  other.
- The model times out or errors → the approval still succeeds; translation can be retried.
- **Never assert exact model output.** Assert shape, language, length bounds and the invariants.

### Visit counter

- The same visitor hash twice in a day counts once; a new day's salt counts again.
- The raw IP never reaches Redis: assert on what the fake store received.
- Redis down → `POST /api/visit` fails quietly for the visitor, `GET /api/stats` returns a
  documented error, and the footer falls back (frontend test).

### Privacy and output safety

- Logs never contain a raw IP, a Turnstile token, a secret or a full review text.
- Review text containing `<script>`, HTML entities or Markdown comes back from the API exactly as
  stored; escaping is the renderer's job, and the renderer renders text.

## What not to test

- **Not the happy path, five ways.** One anchor case is enough.
- **Not the framework, the Redis client or a provider SDK.** Test _your_ code at the seam with
  them, through a fake port.
- **Not exact model output.** Non-deterministic. Shape and invariants only.
- **Not private helpers directly.** Test the public behaviour.
- **No snapshot tests** of generated content.
- **Nothing that passes regardless.** A test with no meaningful assertion, or that mocks the very
  thing under test, is worse than no test.

## Determinism

Unit and application tests must be deterministic. Inject, never reach for:

- the clock (`now` is a parameter; the daily salt depends on it);
- randomness, ids and the salt itself;
- Redis, Turnstile, Telegram and the model (fake ports);
- the network.

A test that calls a real provider is not a unit test. Keep those in a separate, opt-in suite.

## Coverage

Coverage is a floor, not a goal (see the CI ruleset in
[`engineering-guide.md`](engineering-guide.md)). What matters is **branch** coverage of the error
paths above. The domain and application layers are held higher than the adapters; never chase
100% by testing getters.

## A good test for this API

1. Names the boundary or failure it protects, not "it works".
2. Has one clear reason to fail, and fails for that reason.
3. Is deterministic — same result every run, no real network, no wall clock.
4. Asserts shape and invariants for model output, never exact text.
5. Would go red if you broke the behaviour it describes.
