# NF Portal Copilot Docs — site

Astro + Starlight site tooling for the docs at [`docs/`](https://github.com/nf-osi/portal-chatbot/tree/main/docs) on `main`. This branch (`docs`) holds only the site scaffold; the actual content (including `docs/diagrams/`) lives on `main`.

`site/src/content/docs` is empty (just `.gitkeep`) in this branch. Before building, copy `main`'s entire `docs/` folder into place — including `diagrams/`, which sits alongside the markdown so Astro's asset pipeline can resolve image paths correctly under the `/portal-chatbot` base:

```
site/
  src/content/docs/   <- copy main's docs/* here (md, mdx, and diagrams/)
```

## Local development

```sh
git clone https://github.com/nf-osi/portal-chatbot.git repo
cd repo
git worktree add ../site docs        # this branch, as a sibling dir
git worktree add ../main-docs main   # main, for its docs/ folder

cp -r ../main-docs/docs/. ../site/site/src/content/docs/

cd ../site/site
npm install
npm run dev
```

Re-run the `cp` command (after a `git -C ../main-docs pull`) whenever `main`'s docs content changes.

## Build

```sh
cd site
npm run build   # outputs to site/dist/
```

## CI / GitHub Pages

`.github/workflows/deploy-docs.yml` on `main` does the same copy step in CI: it checks out this `docs` branch plus `main`'s `docs/` folder, copies content into place, builds, and deploys via `actions/deploy-pages`. The site is served at `https://nf-osi.github.io/portal-chatbot/`, hence `site`/`base` in `astro.config.mjs`.
