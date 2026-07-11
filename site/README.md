# NF Portal Copilot Docs — site

Astro + Starlight site tooling for the docs at [`docs/`](https://github.com/nf-osi/portal-chatbot/tree/main/docs) on `main`. This branch (`docs`) holds only the site scaffold; the actual content lives on `main`.

`src/content/docs` and `public/diagrams` are **symlinks** pointing at `../../docs` and `../docs/diagrams` respectively (relative to this `site/` directory) — i.e. they expect a `docs/` checkout of `main` to exist as a sibling of `site/`:

```
<some parent dir>/
  docs/     <- from main, content only
  site/     <- this directory, from the docs branch
```

## Local development

Use two `git worktree`s to get both branches checked out as sibling directories, without disturbing your primary clone:

```sh
git clone https://github.com/nf-osi/portal-chatbot.git repo
cd repo

# 1. Check out this branch's site/ as a sibling of repo/
git worktree add ../site docs

# 2. Check out main's docs/ folder only, as a sibling of ../site/
git worktree add ../main-docs main
cd ../main-docs
git sparse-checkout init --cone
git sparse-checkout set docs

# 3. Point the symlink target at that docs/ checkout
ln -s ../main-docs/docs ../site/docs

cd ../site/site
npm install
npm run dev
```

After step 3, `../site/docs` is a real directory (`../main-docs/docs`) sitting next to `../site/site`, which is what the committed symlinks (`../../docs` from `site/src/content/docs`, `../docs/diagrams` from `site/public/diagrams`) resolve to.

To pick up new content later, just `git -C ../main-docs pull`.

## Build

```sh
cd site
npm run build   # outputs to site/dist/
```

## Why `preserveSymlinks: true`

`astro.config.mjs` sets `vite.resolve.preserveSymlinks: true`. Without it, Vite resolves the symlinked content files to their real path outside `site/` before resolving imports (like `@astrojs/starlight/components`), and can't find `site/node_modules` from there. This setting keeps resolution anchored to the symlinked path inside `site/`.
