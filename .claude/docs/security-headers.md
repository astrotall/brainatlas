# Security headers and caching

Normative. Response headers come from `headers()` in `next.config.ts`, next to the rewrites.
There is no `vercel.json` and no `_headers` file. The values live in `src/shared/config`
(`security-headers.ts`, `cache-policy.ts`) and are tested through the real Next config.

## Security headers

Sent on `/:path*`: pages, files from `public/`, the atlas, `/_next/static` and the 404 page. No
narrower rule may set one of them.

| Header                      | Value                                                                |
| --------------------------- | -------------------------------------------------------------------- |
| `Content-Security-Policy`   | see below                                                            |
| `X-Frame-Options`           | `SAMEORIGIN`                                                         |
| `X-Content-Type-Options`    | `nosniff`                                                            |
| `Referrer-Policy`           | `no-referrer`                                                        |
| `Permissions-Policy`        | `fullscreen=(self)`; every other listed feature is denied with `=()` |
| `Strict-Transport-Security` | `max-age=31536000`                                                   |

`X-Powered-By` is switched off (`poweredByHeader: false`).

## Content-Security-Policy

| Directive         | Sources                  | Why                                                       |
| ----------------- | ------------------------ | --------------------------------------------------------- |
| `default-src`     | `'none'`                 | Anything not listed below is blocked.                     |
| `script-src`      | `'self' 'unsafe-inline'` | Next bootstrap scripts and the legacy pages' inline code. |
| `style-src`       | `'self' 'unsafe-inline'` | Next stylesheets and the legacy pages' inline styles.     |
| `img-src`         | `'self' data:`           | The atlas preview and inline images.                      |
| `font-src`        | `'self' data:`           | The atlas embeds its fonts; `next/font` self-hosts later. |
| `connect-src`     | `'self'`                 | The API is same-origin.                                   |
| `frame-src`       | `'self'`                 | The home page embeds the atlas in an iframe.              |
| `object-src`      | `'none'`                 | No plugins.                                               |
| `base-uri`        | `'none'`                 | Nothing uses `<base>`.                                    |
| `form-action`     | `'self'`                 | A form may only submit to this origin.                    |
| `frame-ancestors` | `'self'`                 | Only this site may frame its pages.                       |

The site makes no third-party requests, so no external origin is listed.

### `'unsafe-inline'` stays in `script-src`

Next.js emits small inline bootstrap scripts. A nonce-based policy needs middleware and
per-request rendering, which the Vercel Hobby limits rule out: every page is static. Hash-based
tightening is not done.

**Our own code adds no new inline scripts.** Anything that must run before first paint is a static
file. `'unsafe-inline'` is there for the framework and for the legacy pages, and is not permission
to write more.

### `'unsafe-eval'` exists only under `next dev`

React's development tooling needs it. It is added when Next reports the development server phase,
never in a build or a test. The gate is the phase, not `NODE_ENV`, which a shell can override.

### Adding an origin

Add it to the one directive that needs it, with the reason in the table above and a matching test
change. Cloudflare Turnstile (`challenges.cloudflare.com`) is added by BRA-9 together with the
widget, not before.

## HSTS

One year, **without `includeSubDomains` and without `preload`**. The domain belongs to the team and
may host other subdomains; both directives affect them and cannot be undone quickly.

## Permissions-Policy

`fullscreen` is allowed for this origin because the home page delegates it to the atlas iframe.
The workbook export is a file download, which this header does not govern. A feature the site
starts to use moves from the denied list to the allowed one in the same change. Check the browser
console after editing the list: Chrome warns about names it does not recognise.

## Cache-Control

| Paths                                                               | Value                                                |
| ------------------------------------------------------------------- | ---------------------------------------------------- |
| Home, workbook and quiz pages, short and `.html` forms, and `/`     | `public, max-age=0, must-revalidate`                 |
| Atlas (both forms), `atlas-preview.jpg`, both `LICENSE-*.txt` files | `public, max-age=3600, stale-while-revalidate=86400` |
| `/_next/static`                                                     | set by Next: `public, max-age=31536000, immutable`   |
| `/api/*`                                                            | no rule; each function sets its own                  |
| 404                                                                 | no rule; Next sends `no-store`                       |

- **Pages** revalidate every time, so a change shows at once. An unchanged page costs a `304`.
- **Unhashed files** are fresh for one hour, which covers a study session without downloading the
  1.6 MB atlas again. Chrome applies `stale-while-revalidate` to subresources such as the preview
  image, which may therefore be shown stale once, up to about 25 hours after a change. Page and
  iframe loads, the atlas included, revalidate as soon as the hour is over.
- **Never `immutable`** for a URL without a content hash: learners would keep a stale copy.

## Adding a file to `public/`

Every new file must be registered in `PUBLIC_FILE` (`public-files.ts`) **and** given a policy in
`PUBLIC_FILE_CACHE` (`cache-policy.ts`). An unregistered file fails the public-surface test; a
registered file without a policy fails the typecheck. Unhashed files, such as the upcoming
`public/theme-init.js`, get the moderate policy and never `immutable`. Only the three HTML pages
that are not the atlas revalidate on every request.

## Known limits

- Under `next start`, Next's own `308` redirects (trailing slash, repeated slash) carry none of
  these headers. The page they lead to does.
- Cache rules match the exact file name. A percent-encoded spelling of a file is served with
  Next's default `public, max-age=0`.
- `/api/docs` loads Swagger UI from a third-party host, which this policy blocks wherever it
  applies to the API. The policy is not loosened for it; BRA-6 decides what happens to the docs.
