# NF Portal Copilot Docs

Hugo + [hugo-book](https://themes.gohugo.io/themes/hugo-book/) docs site.

## Local development

```sh
git clone --recurse-submodules https://github.com/nf-osi/portal-chatbot.git
cd portal-chatbot/docs
hugo server
```

If you already cloned without `--recurse-submodules`, fetch the theme with:

```sh
git submodule update --init --recursive
```

## Build

```sh
cd docs
hugo --minify   # outputs to docs/public/, not committed
```

## CI / GitHub Pages

`.github/workflows/deploy-docs.yml` checks out the repo (with submodules), installs Hugo, and builds. The site is served at `https://nf-osi.github.io/portal-chatbot/`, hence `baseURL` in `hugo.toml`.
