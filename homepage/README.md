# `homepage/` — SPECA documentation site (Docusaurus)

Source for the documentation deployed at
[https://nyx.foundation/](https://nyx.foundation/). Built
with [Docusaurus](https://docusaurus.io/).

This is the **single source of truth** for SPECA's user-facing
documentation; the in-repo `*/README.md` files are slim landing pages
that point here.

## Local development

```bash
npm install      # one-time
npm start        # http://localhost:3000 — JP locale only, fast HMR
npm start -- --locale en   # serve the English locale instead

npm run build    # static build for both locales (used by CI)
npm run serve    # serve the built site locally
```

`onBrokenLinks: 'throw'` is on, so a broken link breaks the build —
fix it before pushing.

## Layout

```
homepage/
├── docs/                                   ← Japanese (default locale) doc source
│   ├── intro.md
│   ├── guide/ tutorial/ getting-started/   ← introductory sections
│   ├── pipeline/                           ← phase-by-phase docs
│   ├── concepts/                           ← core ideas (proof-attempt, gates, etc.)
│   ├── references/                         ← paper appendices
│   ├── operations/                         ← operator runbooks (datasets, benchmarks)
│   └── design-notes/                       ← rationale / postmortems
├── i18n/en/                                ← English translations (UI + per-doc overrides)
├── src/                                    ← React components, custom CSS
├── static/                                 ← img/, favicon, etc.
├── docusaurus.config.js                    ← site config + i18n setup
└── sidebars.js                             ← navigation tree
```

## Bilingual (JP + EN)

The site is configured for two locales (`docusaurus.config.js`):

```js
i18n: {
  defaultLocale: 'ja',
  locales: ['ja', 'en'],
}
```

- Default-locale (JP) doc source lives directly under `docs/`.
- English translations live under `i18n/en/`:
  - **UI strings** (navbar / footer / sidebar category labels) are in
    `i18n/en/docusaurus-theme-classic/*.json` and
    `i18n/en/docusaurus-plugin-content-docs/current.json`. Already
    translated.
  - **Doc content** translations belong under
    `i18n/en/docusaurus-plugin-content-docs/current/<same-path-as-docs>.md`.
    Not yet populated — until a page is added there, the EN locale falls
    back to the JP source.

### Workflow for adding / refreshing translations

1. Edit the original JP doc under `homepage/docs/<path>.md`.
2. Add or update the English version at
   `homepage/i18n/en/docusaurus-plugin-content-docs/current/<path>.md`.
3. If you change UI labels (sidebar categories, navbar/footer items),
   regenerate the translation JSONs:
   ```bash
   npm run write-translations -- --locale en
   ```
   Then edit the freshly generated `i18n/en/**/*.json` to fill in the
   English strings (the generator stamps each new key with the JP
   source as a placeholder).

## Deployment

```bash
USE_SSH=true npm run deploy            # SSH route
GIT_USER=<github-username> npm run deploy   # HTTPS route
```

Both routes build and push to the `gh-pages` branch.
