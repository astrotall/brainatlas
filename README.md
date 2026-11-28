# Neuroctivity

Static, bilingual neuroscience learning site for secondary-school students and learners preparing for GCSE/IGCSE, IB, AP Biology and related courses. The content is limited to the biology of the nervous system: anatomy, physiology and neurochemistry.

## Pages

The pages and other public files live in `public/` and are served from the site root exactly as they are.

- `index.html` — course topics, interactive atlas entry point, and the curated external resource library.
- `workbook.html` — bilingual searchable topic guide, topic-specific quizzes with explanations, and private local notes with text export.
- `mozg-3d-atlas-2.html` — the interactive 3D brain atlas: 28 structures, 13 animated processes (memory, stress physiology, reward prediction error, sleep, vision, speech, movement, pain, attention, circadian rhythm, plasticity, hunger, breathing), 9 neurotransmitters, a "find the structure" trainer, search, and reference cards (what is real on the model, limits of the model, licences). Opens with `?mode=<id>` to start on a given topic, for example `?mode=p:memory` or `?mode=c:dopamine`.
- `kira.html` — short, self-contained neuroscience quiz. Answers are not saved.
- `LICENSE-freesurfer.txt` — required licence for the modified surface data.
- `LICENSE-atlas-data.txt` — notices for the other atlas data (MNI152 template, CBIG, three.js).

There is no account system. The API in `api/` has a health check and the published contract for reviews and the visit counter (see [`.claude/backend/api-contract.md`](.claude/backend/api-contract.md)); the pages do not call it yet. Workbook notes and best quiz scores are stored in the browser's local storage on the learner's device; notes can be exported as a text file. Nothing is sent to a server. The atlas has Three.js, its data and the fonts embedded in the page, so it works offline; the fonts are embedded too (Manrope, SIL OFL 1.1; monospaced labels use the system font), so the site makes no third-party requests at all.

The brain atlas always uses a dark interface and 3D viewport for consistent contrast. The light/dark theme preference changes the homepage, workbook, and quiz, but does not affect the atlas. The language choice (`RU / EN`) is shared between all pages.

## Brain model

- **Cortex** — the fsaverage5 pial surface from FreeSurfer: 10,242 vertices per hemisphere, an average of MRI scans of 40 people (a population template, not an individual scan). Cortical zones are highlighted along the gyri of the Desikan–Killiany atlas, transferred to fsaverage5 by spherical registration; hovering over the cortex names the gyrus.
- **Deep structures** — thalamus, striatum, hippocampus, amygdala, nucleus accumbens, brainstem, cerebellum and corpus callosum are surfaces built from the FreeSurfer segmentation of the MNI152 template (ICBM 152 nonlinear, 6th generation; CBIG repository). The corpus callosum follows its real midline profile (genu, rostrum, body, splenium). Small brainstem and hypothalamic nuclei cannot be resolved by MRI at this scale and are drawn schematically at their MNI coordinates; pathways are schematic too.
- Highlight colours identify the role of a region in the chosen topic (activity increased / decreased, structural change, pathway), not measured brain activity.

Attribution: "This product includes FreeSurfer developed by CorTechs Labs, Inc. and The General Hospital Corporation. FreeSurfer © The General Hospital Corporation (Boston, MA)." The full FreeSurfer Software License Agreement is included in `LICENSE-freesurfer.txt`, as required. The atlas itself also shows all notices under "About the model → Licences".

## Embedding on the homepage

The hero of `index.html` embeds the atlas in an iframe with `?embed=1&mode=p:memory`. In embed mode the atlas hides its interface, keeps the camera still and lets the visitor rotate the model. Security headers and cache rules are set in `next.config.ts`; the Content-Security-Policy allows only same-origin framing (see [`.claude/docs/security-headers.md`](.claude/docs/security-headers.md)). If a host blocks the frame, the page detects it and shows `atlas-preview.jpg`, a rendered still of the model, in its place.

## Development

The site is a [Next.js](https://nextjs.org/) App Router app (TypeScript, Tailwind CSS), statically generated and hosted on Vercel; the API is FastAPI in Python Vercel Functions under `/api`. Requires Node.js 22.18+ with pnpm (the version is pinned in `package.json`), and Python 3.12 with [uv](https://docs.astral.sh/uv/) for the API.

```sh
pnpm install            # also installs the git hooks
pnpm dev                # http://localhost:3000
pnpm build              # every route must be listed as static
pnpm start              # serves the build on http://localhost:3000
pnpm run ci             # typecheck + lint + format check + tests

make install            # Python environment from uv.lock
make check test coverage-gate
make run                # API on http://127.0.0.1:8000/api/health, docs at /api/docs
make openapi            # regenerate the committed OpenAPI schema after an API change
pnpm api:generate       # regenerate the frontend API types from it
```

`pnpm dev` forwards `/api/*` to `make run`, so start both when working on anything that calls the API.

Project rules, architecture and the contribution workflow are in [CLAUDE.md](CLAUDE.md), [CONTRIBUTING.md](CONTRIBUTING.md) and [`.claude/`](.claude).

## What is public

Exactly the seven files in `public/`, at the site root. `/` and the short forms `/index`, `/workbook`, `/kira` and `/mozg-3d-atlas-2` are rewrites to the `.html` files, so both forms keep working with their query strings. Everything else in the repository returns 404.

## Deploy

Import the repository in Vercel with the **Next.js** framework preset (the import screen may suggest FastAPI because of `pyproject.toml`; choose Next.js) and the default build settings. There is no `vercel.json`. The one Python function, `api/index.py`, is built from the root `pyproject.toml` and `uv.lock`; `next.config.ts` rewrites every `/api/*` path to it. The interactive API docs are not served on Vercel; `/api/openapi.json` is.

The atlas describes the healthy brain only (anatomy, physiology, neurochemistry) and is not a diagnostic tool. The workbook provides independent practice on concepts relevant to ЕГЭ, GCSE/IGCSE, IB, and AP; it is not an official exam question bank. The external research links are third-party resources. Their content, access requirements, and age suitability are set by their respective publishers; advanced papers should be used with teacher guidance.
