# NF Portal Copilot Docs — site

Astro + Starlight site tooling for the docs at [`docs/`](https://github.com/nf-osi/portal-chatbot/tree/main/docs) on `main`. This branch (`docs`) holds only the site scaffold; the actual content lives on `main`.

`src/content/docs` and `public/diagrams` are empty (just `.gitkeep`) in this branch. Before building, copy `main`'s `docs/` folder into place:

```
site/
  src/content/docs/   <- copy main's docs/*.md, docs/*.mdx here
  public/diagrams/    <- copy main's docs/diagrams/* here
```

## Local development

```sh
git clone https://github.com/nf-osi/portal-chatbot.git repo
cd repo
git worktree add ../site docs        # this branch, as a sibling dir
git worktree add ../main-docs main   # main, for its docs/ folder

cp ../main-docs/docs/*.md ../main-docs/docs/*.mdx ../site/site/src/content/docs/
cp ../main-docs/docs/diagrams/* ../site/site/public/diagrams/

cd ../site/site
npm install
npm run dev
```

Re-run the two `cp` commands (after a `git -C ../main-docs pull`) whenever `main`'s docs content changes.

## Build

```sh
cd site
npm run build   # outputs to site/dist/
```

## CI / GitHub Pages

`.github/workflows/deploy-docs.yml` on `main` does the same copy step in CI: it checks out this `docs` branch plus `main`'s `docs/` folder, copies content into place, builds, and deploys via `actions/deploy-pages`.
