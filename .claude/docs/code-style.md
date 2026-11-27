# Code style

Normative. Match this exactly; do not introduce personal variations.

## Language

- TypeScript only, `strict: true`. There are no `.js`, `.jsx`, `.mjs` or `.cjs` files outside
  `public/`.
- `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` and `noImplicitOverride` are on.
  Handle the resulting `undefined` cases, do not silence them.
- **No comments.** If a block needs explanation, the names are wrong or it belongs in a markdown
  doc. The legacy HTML in `public/` is exempt because it stays byte-identical until it is
  converted.

## Typing

- `any` is banned. Use `unknown` at boundaries and narrow with Zod.
- Non-null assertions (`!`) are banned. Narrow explicitly or return early.
- `as` is banned except immediately after a Zod parse, and in `as const`.
- `interface` for object shapes that are extended or implemented, including component props.
  `type` for unions, intersections, mapped and utility types.
- Prefer union literals over enums. Derive the type from the constant object:

  ```ts
  export const PUBLIC_FILE = {
    HOME: 'index.html',
    ATLAS: 'mozg-3d-atlas-2.html',
  } as const;

  export type PublicFile = (typeof PUBLIC_FILE)[keyof typeof PUBLIC_FILE];
  ```

- Every exported function has an explicit return type. Local functions may infer.
- Model impossible states out of existence with discriminated unions instead of optional fields
  that must be checked together.

## Validation

Every value entering the app from outside is parsed with Zod before use: HTTP responses,
`localStorage` values, URL search params read on the client, and anything from a third-party
script. The Zod schema is the single definition; the TypeScript type is inferred from it with
`z.infer`, never written twice.

## Files and naming

| Thing                | Convention                                 | Example                               |
| -------------------- | ------------------------------------------ | ------------------------------------- |
| Files and folders    | `kebab-case`                               | `review-card.tsx`, `use-reviews.ts`   |
| Components           | `PascalCase`                               | `ReviewCard`                          |
| Hooks                | `useCamelCase`                             | `useReviews`                          |
| Stores               | `useXStore`                                | `useThemeStore`                       |
| Constant objects     | `SCREAMING_SNAKE_CASE`                     | `ROUTE`, `STORAGE_KEY`, `PUBLIC_FILE` |
| Types and interfaces | `PascalCase`, no `I` prefix                | `Review`, `ReviewCardProps`           |
| Zod schemas          | `xSchema`                                  | `reviewSchema`                        |
| Booleans             | `is` / `has` / `can` prefix                | `isPending`, `hasTranslation`         |
| Event handlers       | `handleX` in the component, `onX` in props | `onSubmit`, `handleSubmit`            |

One component per file, and the file is named after it.

## Exports

- Named exports everywhere.
- Default exports appear **only** in Next.js special files under the root `app/` (`layout.tsx`,
  `page.tsx`, `not-found.tsx`, …) and in tool config files that require one
  (`next.config.ts`, `eslint.config.ts`, `vitest.config.ts`).

## Server and Client Components

- **Server Components by default.** A component is a Server Component unless it needs state,
  effects, browser APIs or event handlers.
- `'use client'` goes on the **leaves** that need it — the toggle, the form, the counter — never
  on a layout, a screen or a widget just because one child is interactive. Pass server-rendered
  children into a client component through `children` instead of moving the parent to the client.
- A client component never imports server-only code. Data a client leaf needs arrives as
  serialisable props or through TanStack Query.

## Static rendering

Every route is statically generated (Vercel Hobby budget). The root layout sets
`dynamic = 'error'`, so the build fails if any of these appear in server code:

- `cookies()`, `headers()`, `draftMode()`, `connection()`;
- reading `searchParams` in a page;
- `fetch` with `cache: 'no-store'` or `revalidate: 0`, or `export const revalidate = 0`;
- a dynamic route segment without `generateStaticParams`.

Anything per-visitor (language, theme, the visit counter, reviews) happens on the client, after
hydration, against `/api`.

## Components

```tsx
interface ReviewCardProps {
  review: Review;
  onReport: (reviewId: string) => void;
}

export const ReviewCard = ({ review, onReport }: ReviewCardProps): ReactNode => {
  const { t } = useTranslation('reviews');

  const handleReport = useCallback(() => {
    onReport(review.id);
  }, [review.id, onReport]);

  return (
    <article className="rounded-3xl bg-surface p-4 dark:bg-surface-dark">
      <p className="text-base text-foreground dark:text-foreground-dark">{review.text}</p>
      <button type="button" className="text-sm text-muted" onClick={handleReport}>
        {t('actions.report')}
      </button>
    </article>
  );
};
```

The translation hook above is illustrative; the i18n library is chosen in BRA-3.

Rules:

- Arrow function assigned to a `const`, props destructured in the signature.
- Props interface named `<Component>Props`, declared directly above the component.
- No inline object or array literals in JSX props — they allocate on every render.
- No anonymous functions passed to a child that is memoised.
- Early return for loading and empty states rather than nested ternaries in JSX.
- Order inside a component: hooks, derived values, callbacks, effects, early returns, JSX.
- Review text and any other visitor-supplied string is rendered as a text child, never through
  `dangerouslySetInnerHTML`.

## One component per file, and never nested

Inline JSX inside a `return` is fine — you are not required to shred a layout into
sub-components. The rule fires the moment you pull a piece out as a `<Child />`: it moves to its
own file under `ui/`, named after it, and is imported. A second component declared in the same
file is not allowed.

Never declare a component or a hook inside another component's body. It is recreated on every
render, loses its identity, and `react-hooks/static-components` rejects it. Components and hooks
live at module top level or in their own file. Only the slice's public entry point is exported
from `index.ts`; private sub-components are imported by relative path inside the slice.

## When a component is doing too much

Split it — logic into a hook in the slice's `model/`, UI pieces into their own files under
`ui/` — as soon as any one of these is true:

- its JSX runs past roughly 100 lines and you scroll to follow the structure;
- more than four or five `useState` sit together;
- more than two `useEffect` watch different things;
- two levels of abstraction share the file — a screen skeleton next to a single control's markup;
- business logic and presentation are mixed — the component knows a query key, a validation rule
  and a border colour at once;
- you catch yourself copy-pasting markup or a `handleX` into another file — it belongs in
  `shared`;
- a prop is drilled through three levels for one line at the bottom.

## Styling

- Tailwind utility classes only. Inline `style` objects only where Tailwind cannot express it.
- All colours, spacing, radii and font sizes come from the Tailwind theme tokens (defined in
  `src/app/styles/globals.css` with `@theme` from BRA-3). Never a raw hex value or a raw pixel
  number in a component.
- Dark mode is supported by every component from the moment it is written, via `dark:`. There is
  no retrofit pass. The theme is applied before first paint so there is no flash (see
  `state-management.md`).
- Tailwind scans only `src/` (`@import 'tailwindcss' source('../..')`); the legacy HTML in
  `public/` is not scanned and carries its own styles.

## Lists

- `key` is a stable domain id, never the index.
- Long lists (the review wall) are paginated by the API, not rendered in full.

## Performance

- `useCallback` for any function passed to a memoised child or into a dependency array. Do not
  wrap functions that are only called locally.
- `useMemo` only for genuinely expensive work or referential stability, not for arithmetic.
- Subscribe to Zustand with a narrow selector. ESLint rejects `useXStore()` and selectors that
  return a new object literal. See `state-management.md`.
- Ship the smallest client bundle that works: a Server Component costs nothing on the client.

## Async and errors

- `async/await`, never raw `.then()` chains.
- Never swallow an error. Either surface it to the visitor through a translated message or
  rethrow it so a boundary handles it.
- Errors thrown by the API layer are typed application errors, not raw fetch failures.
- No `useEffect` for data fetching. That is TanStack Query's job.
- `useEffect` is a last resort in general. Prefer deriving during render, event handlers, or a
  store subscription.

## Testing

- Vitest, `*.test.ts` next to the code it protects.
- Config and routing invariants (public surface, legacy URLs, pinned checksums, storage keys) are
  tested against the real files, not mocks.
- Zod schemas covering API responses have a test with a realistic fixture.
- Snapshot tests are not used.

## Before you finish

1. Types pass with no new errors.
2. No `any`, `!`, unexplained `as`, or comments were introduced.
3. No user-facing string literal was introduced outside a locale file.
4. No new magic string that should have gone into `src/shared/config`.
5. `pnpm build` still lists every route as static.
6. No unrelated file was modified.
