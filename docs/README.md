# NF Portal Copilot Docs — site

Astro + Starlight site tooling for the docs at [`docs/`](https://github.com/nf-osi/portal-chatbot/tree/main/docs). `site/src/content/docs` is a symlink to the repo's top-level `docs/`, so content and site scaffold live together on this branch — no cross-branch copy step needed.

## Local development

```sh
git clone https://github.com/nf-osi/portal-chatbot.git
cd portal-chatbot/docs
npm install
npm run dev
```

## Build

```sh
cd docs
npm run build   # outputs to site/dist/
```

## CI / GitHub Pages

`.github/workflows/deploy-docs.yml` checks out the repo, installs, and builds — no separate content checkout or copy step. The site is served at `https://nf-osi.github.io/portal-chatbot/`, hence `site`/`base` in `astro.config.mjs`.
