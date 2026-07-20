# NF Portal Copilot Docs

Astro + Starlight docs and site tooling.

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
npm run build   # outputs to site/dist/, not committed
```

## CI / GitHub Pages

`.github/workflows/deploy-docs.yml` checks out the repo, installs, and builds. The site is served at `https://nf-osi.github.io/portal-chatbot/`, hence `site`/`base` in `astro.config.mjs`.
