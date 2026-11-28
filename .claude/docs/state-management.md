# State management

Three owners exist. Mixing them up is the fastest way to get hydration errors, a theme flash or
two copies of the same data drifting apart. Decide which one owns a piece of state before writing
it.

TanStack Query arrives with BRA-9 and Zustand with BRA-3. Neither is installed yet; this document
is the contract they are introduced under.

## Ownership

| State                                                 | Owner                                     | Why                                                           |
| ----------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------- |
| Reviews, the visit counter, anything served by `/api` | **TanStack Query**                        | Server state: it lives in Redis behind the API.               |
| Interface language, theme                             | **Zustand**, persisted to `localStorage`  | Small, read everywhere, survives a reload.                    |
| UI state shared by several slices (an open dialog)    | **Zustand**                               | Ephemeral, dies with the page.                                |
| Workbook notes and best quiz scores                   | **`localStorage`**, owned by the workbook | Private to the visitor's device. Nothing is sent to a server. |
| Form field values, a collapsed panel, a draft review  | **Local `useState`**                      | Never lift a text input into a global store.                  |

The rule that matters most: **server state is never copied into a store.** A review list in
Zustand "for speed" drifts from the server and you end up reconciling two sources. Query owns it;
components read it through a query hook.

## localStorage keys

The keys are fixed by the legacy pages, and existing visitors already have values under them:

| Key                        | Holds                          | Format                        |
| -------------------------- | ------------------------------ | ----------------------------- |
| `conn_lang`                | `ru` or `en`                   | plain string                  |
| `neuroctivity-theme`       | the theme choice               | plain string                  |
| `neuroctivity-workbook-v1` | workbook notes and best scores | as written by `workbook.html` |

- The keys come from `STORAGE_KEY` in `src/shared/config`. A test checks the legacy pages still
  use the same literals.
- Language and theme stay **plain strings**. Zustand's `persist` middleware wraps values in JSON
  (`{"state":…,"version":…}`) by default, which would break the legacy pages reading the same key
  and lose every visitor's setting. Use a custom storage adapter that reads and writes the raw
  string, and parse what it reads with Zod (an unknown value falls back to the default).
- Reading `localStorage` can throw (private mode, disabled storage). Catch it and fall back to
  the default, as the legacy pages do.

## Hydration and the theme flash

The HTML is generated at build time, so the server cannot know a visitor's theme or language.

- **Theme:** a small static script file loaded in the root layout's `<head>` reads
  `neuroctivity-theme` before first paint and sets the class that `dark:` keys on. Without it the
  page paints light and then switches. It is not inline (see `security-headers.md`). The `<html>`
  element gets `suppressHydrationWarning` for that one attribute only.
- **Language:** the static HTML is rendered in the default locale. A client leaf reads
  `conn_lang` after hydration and switches. Never read `localStorage` during render — the server
  output and the first client render must match.
- Components that depend on persisted client state render a stable placeholder until the store
  has hydrated, rather than guessing and correcting.

## TanStack Query

Used exclusively for the same-origin API under `/api`.

### Query keys

Never write a key array inline. Every key comes from `src/shared/config/query-keys.ts` (created
with the first query).

```ts
import { QUERY_KEY } from '@/shared/config';

useQuery({
  queryKey: QUERY_KEY.reviews.list(locale),
  queryFn: () => fetchReviews(locale),
});
```

Key structure is hierarchical so a broad invalidation cascades:

```
[REVIEWS]                      everything review-related
[REVIEWS, 'list', locale]      one locale's approved reviews
[STATS, 'visits']              the visit counter
```

### Defaults

Set once on the `QueryClient` in `src/app/providers`:

- `staleTime` 60 seconds.
- `retry` 2 with exponential backoff; never retry a 4xx.
- Responses are parsed with Zod in the `api/` segment before they reach a component.

### Mutations

- Submitting a review sends the Turnstile token with the request. A `429` surfaces a translated
  "try again later" message, not a generic error.
- A submitted review is `pending`. Do not optimistically insert it into the approved list.
- On success, invalidate the narrowest key that covers the change.

## Zustand

- One store per concern, in the `model/` segment of the slice that owns it.
- **Always select narrowly.** Reading the store object re-renders the component on every unrelated
  change. ESLint enforces this:

  ```ts
  const theme = useThemeStore((state) => state.theme); // correct
  const { theme } = useThemeStore(); // forbidden
  ```

- Select multiple fields with `useShallow`, not by returning a new object literal.
- Actions live in the store next to the state they mutate. Components call actions; they do not
  call `set` themselves.
- Never store derived state. Compute it in a selector.
- Keep genuinely local state next to the component that owns it with `useState`. Promote it into
  a store only when more than one slice must see a consistent view of it.
