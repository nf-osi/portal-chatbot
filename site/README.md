# NF Portal Copilot Docs — site

Astro + Starlight site tooling for the docs at [`docs/`](https://github.com/nf-osi/portal-chatbot/tree/main/docs) on `main`. This branch (`docs`) holds only the site scaffold; the actual content (including `docs/diagrams/`) lives on `main`.

`site/src/content/docs` is empty (just `.gitkeep`) in this branch. Before building, pull `main`'s `docs/` folder into place with `copy-content.sh`, which uses `git archive` so it works from a single clone — no second worktree needed:

```sh
./copy-content.sh                # copies docs/ from origin/main
./copy-content.sh origin/some-branch  # or from any other branch/tag/commit
```

## Local development

```sh
git clone https://github.com/nf-osi/portal-chatbot.git
cd portal-chatbot
git switch docs   # `git checkout docs` is ambiguous — main also has a docs/ folder
cd site

./copy-content.sh
npm install
npm run dev
```

Re-run `./copy-content.sh` whenever `main`'s docs content changes.

## Build

```sh
cd site
./copy-content.sh
npm run build   # outputs to site/dist/
```

## CI / GitHub Pages

`.github/workflows/deploy-docs.yml` on `main` does the equivalent in CI (checks out this `docs` branch plus `main`'s `docs/` folder, copies content into place, builds, deploys via `actions/deploy-pages`). The site is served at `https://nf-osi.github.io/portal-chatbot/`, hence `site`/`base` in `astro.config.mjs`.
