# Feature-Sliced Design

The site follows FSD. This document is the authority on where a file belongs and what it is
allowed to import.

## Layers

From highest to lowest. A module may import **only from strictly lower layers**.

| Layer    | Directory      | Holds                                                       | Example                                  |
| -------- | -------------- | ----------------------------------------------------------- | ---------------------------------------- |
| app      | `src/app`      | Root layout, providers, global styles, root composition     | `RootLayout`, `QueryProvider`            |
| screens  | `src/screens`  | One composition per route. No business logic.               | `HomeScreen`, `WorkbookScreen`           |
| widgets  | `src/widgets`  | Self-contained blocks composed of several features/entities | `SiteHeader`, `SiteFooter`, `ReviewWall` |
| features | `src/features` | One user action, with its own state and mutation            | `submit-review`, `switch-language`       |
| entities | `src/entities` | Domain nouns: schema, queries, selectors, dumb presentation | `review`, `topic`, `quiz`                |
| shared   | `src/shared`   | Reusable, domain-agnostic infrastructure                    | `ui`, `lib`, `api`, `i18n`, `config`     |

`processes` is deliberately unused. If a multi-step flow appears, it goes in `widgets` until
there is a second consumer.

### The Next.js `app/` collision

Next.js owns a top-level `app/` directory and FSD also names a layer `app`. The resolution:

- The repo-root `app/` contains **route files only** (`layout.tsx`, `page.tsx`, `not-found.tsx`,
  …). Each one is a thin re-export and uses a default export because Next requires it.
- The FSD `app` layer lives at `src/app/`.
- The FSD `pages` layer is named `screens`, as in the sister project. There is no `pages/`
  directory anywhere.

Next.js looks for `app/` or `pages/` in the repo root first and **ignores `src/app` and
`src/pages` when a root `app/` exists**. That is what keeps our providers from being treated as
routes. Two things must therefore stay true, and `src/app/route-directories.test.ts` checks both:

- the root `app/` directory exists;
- there is no `pages/` or `src/pages/` directory (Next would build it as Pages Router routes).

A route file looks exactly like this:

```tsx
export { HomeScreen as default } from '@/screens/home';
```

The one permitted addition is **route segment config**, which Next reads statically and only from
the route file itself, so it cannot be re-exported. Today that is the root layout:

```tsx
export { RootLayout as default } from '@/app';

export const dynamic = 'error';
```

`metadata` and `generateStaticParams` follow the same rule when they are needed: build the value
in `src/` and export it from the route file. If you find markup, hooks or logic inside `app/`,
move it into `src/screens` or `src/app`.

## Slices

A slice is a business domain folder inside a layer. `shared` and `app` have no slices, only
segments.

Slice folders are `kebab-case`: `submit-review`, `switch-language`.

## Segments

Inside a slice, code is grouped by technical purpose:

| Segment    | Contains                                                  |
| ---------- | --------------------------------------------------------- |
| `ui/`      | React components                                          |
| `model/`   | Zustand stores, selectors, domain types, pure state logic |
| `api/`     | TanStack Query hooks, HTTP calls                          |
| `lib/`     | Slice-local helpers with no React dependency              |
| `config/`  | Slice-local constants                                     |
| `index.ts` | The slice's public API                                    |

Only create the segments you actually need. No empty folders.

## Import rules

Enforced by `eslint-plugin-boundaries` in `eslint.config.ts`. Violations fail the build.

1. **Downward only.** `features` may import `entities` and `shared`. `entities` may import
   `shared`. `shared` imports nothing from the app. Route files in `app/` may import only
   `src/app` and `src/screens`.
2. **No cross-imports on the same layer.** `features/submit-review` may not import
   `features/switch-language`. If two features need the same thing, it belongs one layer down.
3. **Public API only.** Import from the slice (or `shared` segment) root, never from its
   internals. This applies to `shared` too: `@/shared/config`, never `@/shared/config/routes`.

   ```ts
   import { ReviewCard } from '@/entities/review'; // correct
   import { ReviewCard } from '@/entities/review/ui/review-card'; // forbidden
   ```

4. **Never import your own slice through its barrel.** Inside `entities/review`, use relative
   paths (`../model/review.types`). Importing `@/entities/review` from within itself creates a
   cycle.
5. **`index.ts` re-exports only what other layers need.** It is a curated surface, not a dump of
   every file. No `export *`.

## Path aliases

Configured in `tsconfig.json`:

```
@/app/*        @/screens/*    @/widgets/*
@/features/*   @/entities/*   @/shared/*
```

`next.config.ts` cannot resolve the alias; it imports `./src/shared/config` by relative path.
Never use relative paths that climb out of a slice (`../../../entities/review`). Use the alias.

## Where does this file go?

Answer in order; the first match wins.

1. Does it render a full route? → `screens`
2. Is it a large block reused across screens, composed of several features? → `widgets`
3. Does it perform a user action that changes state (a submit, a toggle, a vote)? → `features`
4. Does it describe or display a domain noun without acting on it? → `entities`
5. Is it domain-agnostic and reusable in any project? → `shared`

If a component is used by exactly one screen and does not fit the above, keep it inside that
screen's slice under `ui/`. Do not promote it to `widgets` until a second consumer exists.

## Anti-patterns

- A `components/` or `utils/` folder outside `shared` — segments already cover this.
- Business logic inside `screens` — a screen composes, it does not decide.
- An entity importing a feature — the most common inversion. If an entity component needs an
  action, the parent passes it in as a prop.
- A "god" slice named `common`, `helpers` or `misc`.
- Barrel files that re-export an entire directory.
- Markup or hooks in a route file under `app/`.
