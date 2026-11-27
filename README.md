# Neuroctivity

Static, bilingual neuroscience learning site for secondary-school students and learners preparing for GCSE/IGCSE, IB, AP Biology and related courses. The content is limited to the biology of the nervous system: anatomy, physiology and neurochemistry.

## Pages

- `index.html` — course topics, interactive atlas entry point, and the curated external resource library.
- `workbook.html` — bilingual searchable topic guide, topic-specific quizzes with explanations, and private local notes with text export.
- `mozg-3d-atlas-2.html` — the interactive 3D brain atlas: 28 structures, 13 animated processes (memory, stress physiology, reward prediction error, sleep, vision, speech, movement, pain, attention, circadian rhythm, plasticity, hunger, breathing), 9 neurotransmitters, a "find the structure" trainer, search, and reference cards (what is real on the model, limits of the model, licences). Opens with `?mode=<id>` to start on a given topic, for example `?mode=p:memory` or `?mode=c:dopamine`.
- `kira.html` — short, self-contained neuroscience quiz. Answers are not saved.
- `LICENSE-freesurfer.txt` — required licence for the modified surface data.
- `LICENSE-atlas-data.txt` — notices for the other atlas data (MNI152 template, CBIG, three.js).

There is no build step, account system, or API. Workbook notes and best quiz scores are stored in the browser's local storage on the learner's device; notes can be exported as a text file. Nothing is sent to a server. The atlas has Three.js, its data and the fonts embedded in the page, so it works offline; the fonts are embedded too (Manrope, SIL OFL 1.1; monospaced labels use the system font), so the site makes no third-party requests at all.

The brain atlas always uses a dark interface and 3D viewport for consistent contrast. The light/dark theme preference changes the homepage, workbook, and quiz, but does not affect the atlas. The language choice (`RU / EN`) is shared between all pages.

## Brain model

- **Cortex** — the fsaverage5 pial surface from FreeSurfer: 10,242 vertices per hemisphere, an average of MRI scans of 40 people (a population template, not an individual scan). Cortical zones are highlighted along the gyri of the Desikan–Killiany atlas, transferred to fsaverage5 by spherical registration; hovering over the cortex names the gyrus.
- **Deep structures** — thalamus, striatum, hippocampus, amygdala, nucleus accumbens, brainstem, cerebellum and corpus callosum are surfaces built from the FreeSurfer segmentation of the MNI152 template (ICBM 152 nonlinear, 6th generation; CBIG repository). The corpus callosum follows its real midline profile (genu, rostrum, body, splenium). Small brainstem and hypothalamic nuclei cannot be resolved by MRI at this scale and are drawn schematically at their MNI coordinates; pathways are schematic too.
- Highlight colours identify the role of a region in the chosen topic (activity increased / decreased, structural change, pathway), not measured brain activity.

Attribution: "This product includes FreeSurfer developed by CorTechs Labs, Inc. and The General Hospital Corporation. FreeSurfer © The General Hospital Corporation (Boston, MA)." The full FreeSurfer Software License Agreement is included in `LICENSE-freesurfer.txt`, as required. The atlas itself also shows all notices under "About the model → Licences".

## Embedding on the homepage

The hero of `index.html` embeds the atlas in an iframe with `?embed=1&mode=p:memory`. In embed mode the atlas hides its interface, keeps the camera still and lets the visitor rotate the model. Security headers live in `_headers` only (the `netlify.toml` header block was removed so the two files cannot disagree); they allow same-origin framing (`frame-ancestors 'self'`, `X-Frame-Options: SAMEORIGIN`). If a host still blocks the frame, the page detects it and shows `atlas-preview.jpg`, a rendered still of the model, in its place.

## Deploy

Upload the folder as a static site. For Netlify, the publish directory is `.` and the build command is empty. A local preview can be started with any static HTTP server, for example:

```sh
python3 -m http.server 8765
```

Open `http://127.0.0.1:8765/`.

The atlas describes the healthy brain only (anatomy, physiology, neurochemistry) and is not a diagnostic tool. The workbook provides independent practice on concepts relevant to ЕГЭ, GCSE/IGCSE, IB, and AP; it is not an official exam question bank. The external research links are third-party resources. Their content, access requirements, and age suitability are set by their respective publishers; advanced papers should be used with teacher guidance.
