# API contract

The contract the site (BRA-8 footer counter, BRA-9 review form and list) builds against. Status
per endpoint is in the table below: **implemented** endpoints behave as described; **planned**
endpoints are registered with their final request and response models, validate their input, and
answer `501 not_implemented` until their ticket lands. They carry the `planned` tag in OpenAPI.

## Source of truth

The OpenAPI 3.1 schema that FastAPI generates from the Pydantic models in
`backend/src/neuroctivity/transport`. It is committed as
[`openapi.json`](openapi.json) and served at `/api/openapi.json`. This file is the human summary;
when they disagree, the code wins and this file is fixed in the same change.

| Artifact                              | Produced by         | Checked by                                                |
| ------------------------------------- | ------------------- | --------------------------------------------------------- |
| `.claude/backend/openapi.json`        | `make openapi`      | `make check` (`openapi-check`) fails when it drifts       |
| `src/shared/api/generated/schema.ts`  | `pnpm api:generate` | `pnpm api:check` (part of `pnpm run ci`) fails when stale |
| Response bodies and declared statuses | the routes          | backend contract tests validate them against the file     |

The generator is deterministic (keys sorted, two-space indent, trailing newline), so the diff of
`openapi.json` in a pull request _is_ the contract change. The frontend imports types only from
`@/shared/api` (`ApiSchemas`, `ApiPaths`, `ApiOperations`), never from the generated file.

There is no hand-written schema. There is no CORS: the API is same-origin (`/api/*`).

## Endpoints

| Method | Path                | Status      | Ticket | Success                                    | Errors                  |
| ------ | ------------------- | ----------- | ------ | ------------------------------------------ | ----------------------- |
| `GET`  | `/api/health`       | implemented | BRA-1  | `200 {"status": "ok"}`                     | 405, 500                |
| `GET`  | `/api/reviews`      | implemented | BRA-6  | `200 ReviewList`                           | 422, 503, 500           |
| `POST` | `/api/reviews`      | implemented | BRA-6  | `202 {"status": "pending"}`                | 403, 422, 429, 503, 500 |
| `POST` | `/api/visit`        | planned     | BRA-8  | `204`, no body                             | 429, 501, 503, 500      |
| `GET`  | `/api/stats`        | planned     | BRA-8  | `200 {"today": n, "total": n}`             | 501, 503, 500           |
| `GET`  | `/api/openapi.json` | implemented | BRA-6  | the schema                                 | 405                     |
| `POST` | (webhook)           | planned     | BRA-7  | Telegram moderation; not in the schema yet | —                       |

Every `GET` also answers `HEAD` with the same status and headers and an empty body. Any other
path under `/api` is `404 not_found`; a known path with the wrong method is
`405 method_not_allowed` with an `Allow` header listing the methods it accepts (`HEAD` included
wherever `GET` is). Trailing slashes are not redirected: `/api/health/` is `404`.

## Reviews

### `GET /api/reviews?lang=ru|en&limit=`

| Parameter | Required | Values                              |
| --------- | -------- | ----------------------------------- |
| `lang`    | yes      | `ru`, `en` — the language to return |
| `limit`   | no       | integer `1`–`100`, default `50`     |

`limit` is a plain decimal (`5`, not `05`, `5.0`, `+5`, `1e1`). An unknown parameter, or any
parameter given twice, is `422`: a query the contract does not describe cannot be used to bust the
cache.

```json
{
  "items": [
    {
      "id": "0b6f7c1e-4a3d-4f2e-9c8b-7a6d5e4f3a21",
      "rating": 5,
      "text": "Отличный курс.",
      "lang": "ru",
      "translated": false,
      "createdAt": "2026-11-28T09:15:00Z"
    }
  ]
}
```

- Approved reviews only, newest first. A pending or rejected review is never in the list, in any
  language.
- `lang` is the language of the returned `text`; `translated` is `true` when that text is a
  translation of the original. A review whose translation is missing is returned in its original
  language with `translated: false`.
- `id` is a UUID, `createdAt` is RFC 3339 in UTC.
- The list is wrapped in `items` so a cursor can be added later without a breaking change.
- Render `text` as plain text, never as HTML or Markdown.

### `POST /api/reviews`

```json
{ "rating": 5, "text": "Отличный курс.", "lang": "ru", "turnstileToken": "…" }
```

| Field            | Rule                                                                      |
| ---------------- | ------------------------------------------------------------------------- |
| `rating`         | JSON integer `1`–`5`. Not `"5"`, not `5.0`, not `true`.                   |
| `text`           | string, `10`–`1000` Unicode code points after normalization (below)       |
| `lang`           | `ru` or `en`: the UI language at submit time, declared language of `text` |
| `turnstileToken` | string, `1`–`2048` characters, from the Turnstile widget                  |

- Content type `application/json` (a `charset` parameter and `+json` types are accepted). Any
  other type is `422` with `fields: [{"field": "body", "reason": "invalid"}]`.
- The body is at most **16 KiB**; a larger one is `422` with `reason: "too_long"` on `body`,
  before it is parsed.
- Unknown fields are rejected (`reason: "unknown_field"`).
- Length is counted in code points: `[...text].length` in JavaScript, not `text.length`. An emoji
  outside the BMP counts as one. The limits apply **after normalization**, and the stored text is
  the normalized text:
  1. line breaks become `\n`; tab, vertical tab and form feed become a space;
  2. control, invisible format (zero-width space, bidi overrides, BOM, soft hyphen, tag
     characters), surrogate and private-use characters are removed;
  3. NFC; at most 4 combining marks in a row are kept;
  4. a zero-width joiner survives only between two visible characters (emoji sequences such as
     👩‍🔬 stay intact);
  5. more than one blank line in a row becomes one blank line;
  6. leading and trailing whitespace is trimmed.

  NFKC is **not** applied to the stored text (it would turn `№` into `No` and `10²` into `102`);
  it is used only inside the link check. The form should show the same counter, but the server is
  the authority: a text that looks long enough can still be `too_short` after normalization.

- **No links** (`reason: "links_not_allowed"`): any `scheme://`, `mailto:`, `javascript:`,
  `data:type/`, `tel:+digits`, `www.`, `t.me/` and other messenger links, e-mail addresses, and
  bare domains with a known suffix (`example.com`, `пример.рф`, `site.io`), including fullwidth
  dots, `(dot)` / `[.]` spellings and Cyrillic look-alike letters. Suffixes that are also ordinary
  words (`.it`, `.so`, `.me`, `.live`, `.сайт` …) count only in lowercase, so `good.It helped`,
  `т.е.`, `e.g.`, `Node.js`, `г.Москва` and `3.5` are fine. Moderation remains the real gate;
  `example . com` with spaces is not caught.
- Success is `202 {"status": "pending"}`. The review is not visible until a moderator approves it
  (BRA-7).
- The checks run cheapest first: size and content type, schema and text rules, client address,
  Turnstile, the single-use token claim, then the rate limit, then the write. Invalid input never
  reaches Cloudflare or Redis, and a failed human check never spends the rate budget.

### Turnstile

| Cloudflare answer                                                                   | API                       |
| ----------------------------------------------------------------------------------- | ------------------------- |
| `success: true` (and, when `TURNSTILE_HOSTNAMES` is set, a listed host)             | continues                 |
| `invalid-input-response`, `timeout-or-duplicate`, `missing-input-response`, no code | `403 turnstile_failed`    |
| a token already used here (claimed in Redis for 300 s)                              | `403 turnstile_failed`    |
| `success: true` for an unlisted host                                                | `403 turnstile_failed`    |
| `invalid-input-secret`, `internal-error`, `bad-request`, any unknown code           | `503 service_unavailable` |
| timeout (3 s), network error, non-200, malformed JSON                               | `503 service_unavailable` |

Only the secret and the token are sent; the visitor's IP is not. Cloudflare's own reuse detection
is eventually consistent, so the API also claims each token (its SHA-256) once in Redis: two
concurrent posts with one token store one review. Cloudflare's always-pass test secret accepts
**any** token, not only the dummy one, so test keys must never reach production (the API refuses
them there).

### Rate limits

| Window                 | Default | Variable                      |
| ---------------------- | ------- | ----------------------------- |
| per client, clock hour | 3       | `REVIEW_LIMIT_PER_HOUR`       |
| per client, UTC day    | 10      | `REVIEW_LIMIT_PER_DAY`        |
| all clients, UTC day   | 200     | `REVIEW_GLOBAL_LIMIT_PER_DAY` |

Fixed windows. Over any of them is `429 rate_limited` with `Retry-After` set to the seconds until
that window ends. A refused attempt consumes nothing, so a blocked client cannot drain the global
cap. The client is `HMAC-SHA256(CLIENT_HASH_SECRET, address)`, where the address is the **last**
value of `x-vercel-forwarded-for` (set by Vercel and not overwritten by a proxy in front of it;
`x-forwarded-for` and `x-real-ip` are not trusted), IPv6 grouped by its /64, IPv4-mapped IPv6
read as IPv4. A missing or unparsable address is `503`. The raw address is never stored or logged.
One school network shares one IPv4 address and therefore one budget.

### Failure behaviour

- Redis unreachable, slow (2 s) or answering something unexpected: `POST` and `GET` are `503`
  (fail closed). A failure after the rate limit was taken leaves that attempt counted.
- Missing configuration: the endpoints that need it are `503`, `/api/health` and
  `/api/openapi.json` keep working, and the missing variable names are logged at startup.
- **No check uses the `Origin` header.** The site sends `Referrer-Policy: no-referrer`, so a
  same-origin `POST` carries `Origin: null`.

## Visit counter (BRA-8)

- `POST /api/visit` — no body (any body is ignored), `204` with no body. No cookie is set.
- `GET /api/stats` — `{"today": n, "total": n}`, non-negative integers. `total` is the **sum of
  daily unique visitors**: the daily salt rotates and is not kept, so a returning visitor counts
  again on a new day. Label it accordingly ("visits", not "unique people").

## Errors

Every error, including `404`, `405`, validation, and unhandled exceptions, has one shape:

```json
{
  "error": {
    "code": "validation_failed",
    "message": "The request is invalid",
    "fields": [{ "field": "text", "message": "This value is too short", "reason": "too_short" }]
  }
}
```

`fields` appears only on `validation_failed`, at most 20 entries. `field` is the request key the
entry refers to (`rating`, `text`, `lang`, `turnstileToken`, `limit`, `body` for the body as a
whole, or the unknown key itself, truncated to 64 characters).

| Code                  | Status | When                                                            |
| --------------------- | ------ | --------------------------------------------------------------- |
| `validation_failed`   | 422    | body, query or content type does not match the schema           |
| `turnstile_failed`    | 403    | the Turnstile token is invalid, expired or already used         |
| `rate_limited`        | 429    | over a limit; `Retry-After` gives the seconds to wait           |
| `not_found`           | 404    | no route at this path                                           |
| `method_not_allowed`  | 405    | the path exists, the method does not; `Allow` lists the methods |
| `service_unavailable` | 503    | Redis or Cloudflare cannot answer, or configuration is missing  |
| `not_implemented`     | 501    | a planned endpoint (`/api/visit`, `/api/stats`) before BRA-8    |
| `internal`            | 500    | anything unexpected                                             |

| Field `reason`      | Meaning                                     |
| ------------------- | ------------------------------------------- |
| `missing`           | a required field or the body is absent      |
| `invalid`           | wrong type, value outside the enum or range |
| `too_short`         | below the minimum length                    |
| `too_long`          | above the maximum length                    |
| `links_not_allowed` | the text contains a link                    |
| `unknown_field`     | a field the contract does not declare       |

- The client maps `code` and `reason` to translated messages and **never renders `message`**,
  which is English and exists for logs and curl.
- No error contains a stack trace, a submitted value, a Redis or provider message, or a secret.
- Codes and reasons are stable. A new one is a contract change.

## Headers and caching

| Response                     | `Cache-Control`                                   |
| ---------------------------- | ------------------------------------------------- |
| `GET /api/reviews` `200`     | `public, s-maxage=60, stale-while-revalidate=300` |
| everything else, every error | `no-store`                                        |

Every API response also carries `X-Content-Type-Options: nosniff`, and the site-wide security
headers from `next.config.ts` apply to `/api/*` like any other path. The CSP is not loosened for
the API.

## Routing

All of `/api/*` reaches one Python function, `api/index.py`, through two rewrites in
`next.config.ts` (`src/shared/config/routes.ts` → `API_REWRITES`):

| Request             | Rewritten to                     |
| ------------------- | -------------------------------- |
| `/api`              | `/api/index?__path=`             |
| `/api/:__api_path*` | `/api/index?__path=:__api_path*` |

The app's `RestoreForwardedPath` middleware strips the two **reserved** query parameters, `__path`
and `__api_path`, and when the function sees `/api/index` it routes the path given by the first
`__path`. Clients never send either; a client-sent `__path` cannot change the route, and a
client-sent `__api_path` is discarded.

**Finding from the first deploy.** Vercel appends every named parameter of a rewrite's source to
the destination query, even when the destination already uses it. With the source written as
`/api/:path*`, `GET /api/reviews?lang=ru` reached the function as
`/api/index?__path=reviews&path=reviews&lang=ru` (visible in `x-nextjs-rewritten-query`), and the
app rejected `path` as an unknown parameter (`422`). Local `next start` and Next's config test
helpers do not append it, which is why the local suite missed it. The source parameter is
therefore named `__api_path`, a reserved name the middleware strips. Every other parameter name
keeps its normal meaning: `GET /api/reviews?lang=ru&path=x` is still `422 unknown_field` on
`path`. The backend tests replay Vercel's query shape, and a Vitest guard fails if a rewrite
introduces any parameter name other than the two reserved ones.

## Interactive docs

`/api/docs` (Swagger UI) loads its assets from a CDN that the CSP blocks, so it is **not served
on any deployed environment**. It is enabled only by `API_DOCS_ENABLED=true`, which `make run`
sets, and it is refused whenever `VERCEL` is set, whatever the flag says. Locally:
`http://127.0.0.1:8000/api/docs`. `/api/openapi.json` is served everywhere.

## Local development

`make run` serves the API on `http://127.0.0.1:8000` with the in-memory store
(`STORAGE_BACKEND=memory`), the socket address as the client (`CLIENT_IP_SOURCE=peer`),
Cloudflare's always-pass test secret, the replay guard off and a fresh random
`CLIENT_HASH_SECRET` per run; each can be overridden from the shell. Use the test site key
`1x00000000000000000000AA` in the widget; it yields `XXXX.DUMMY.TOKEN.XXXX`. Under `pnpm dev` (and only there:
`next dev` with `NODE_ENV=development`), Next proxies `/api/*` to that address, so the site calls
`/api/...` same-origin exactly as it will in production. Without `make run`, those calls fail.

## Rules for changing the contract

- An endpoint, field, status, error code or reason changes in the FastAPI models, in
  `openapi.json` (`make openapi`), in the generated types (`pnpm api:generate`) **and** in this
  file, in the same commit.
- A pending review is never visible through any public endpoint.
- Breaking changes are announced in the Jira ticket before they ship, never silently.
