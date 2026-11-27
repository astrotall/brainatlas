# API contract

**Status: stub.** Only `GET /api/health` exists (BRA-1). Everything else below is **planned** and
is defined properly in BRA-6 (reviews) and BRA-8 (visit counter). Shapes are not final until those
tickets land.

## Source of truth

The contract is the **OpenAPI schema FastAPI generates** from the Pydantic request and response
models in `backend/src/neuroctivity/transport`. It is served at `/api/openapi.json`, with the
interactive docs at `/api/docs`. This file is the human-readable summary of it; when they disagree,
the code (and therefore the schema) wins and this file is fixed in the same change.

- There is no hand-written `openapi.yaml`.
- How the frontend gets TypeScript types from the schema (generated in CI, committed, or fetched
  from the deployed site) is decided in BRA-6.
- Locally, `make run` serves the schema at `http://127.0.0.1:8000/api/openapi.json`. On Vercel only
  the `/api/*` paths that have a function are routed to Python; until BRA-6 sets up routing for the
  whole `/api` prefix, `/api/docs` and `/api/openapi.json` are not reachable on the deployed site.

The API is same-origin with the site (`/api/*` on the same domain), so there is no CORS
configuration.

## Endpoints

| Method | Path           | Status      | Ticket | Summary                                                                                  |
| ------ | -------------- | ----------- | ------ | ---------------------------------------------------------------------------------------- |
| `GET`  | `/api/health`  | implemented | BRA-1  | `200 {"status": "ok"}`. Liveness only; reflects dependencies from BRA-6.                 |
| `POST` | `/api/reviews` | planned     | BRA-6  | Create a review as `pending`. Turnstile token + rate limit. `202 {"status": "pending"}`. |
| `GET`  | `/api/reviews` | planned     | BRA-6  | Approved reviews only, `?lang=ru\|en`. Cache headers.                                    |
| `POST` | `/api/visit`   | planned     | BRA-8  | Add the visitor hash to today's HyperLogLog. No cookie. Rate-limited.                    |
| `GET`  | `/api/stats`   | planned     | BRA-8  | Unique visitors today and in total. Short cache.                                         |
| `POST` | (webhook)      | planned     | BRA-7  | Telegram moderation webhook: approve or reject a pending review.                         |

## Planned shapes (BRA-6, not final)

- **Review (public):** `{id, rating, text, lang, translated, createdAt}`. `rating` 1–5; `lang` is
  `ru` or `en`; the text returned depends on `?lang=`; `translated` is `true` when the text is a
  translation of the original.
- **Create review (request):** rating 1–5, text with a length limit (proposed 10–1000 characters,
  to confirm in BRA-6), trimmed, no links, the original language, and the Turnstile token.
- **Error (every endpoint):** `{"error": {"code": "...", "message": "..."}}` with stable
  machine-readable codes and matching HTTP statuses:

  | Code               | Status |
  | ------------------ | ------ |
  | `validation`       | 422    |
  | `turnstile_failed` | 403    |
  | `rate_limited`     | 429    |
  | `not_found`        | 404    |
  | `internal`         | 500    |

  The client maps `code` to a translated message and never renders `message`.

- The limits (rating range, text length, allowed languages) are part of the schema so the frontend
  can read them instead of duplicating them.

## Rules for changing the contract

- An endpoint, field, status code or error code changes in the FastAPI models **and** in this
  file, in the same commit (see `CONTRIBUTING.md` → "What must ship in one commit").
- A pending review is never visible through any public endpoint.
- Breaking changes are announced in the Jira ticket before they ship, never silently.
