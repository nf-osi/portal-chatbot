# Changelog

## nf-portal-copilot

### 2026-06-14 — Harriet

- CloudFormation template for the full Copilot stack, replacing the one removed in #39 (#40)
- Two-stack deployment: `nf-portal-copilot-dev` and `nf-portal-copilot-prod`
- CI/CD workflow: manual dispatch deploys to dev, merge to main deploys to prod
- Added docs KB source selection instructions (#41)
- Optional SPARQL auth token support in Lambda
- Renamed `nf-portal-pilot` → `nf-portal-copilot`

### 2026-04-21 — Amelia (`B0GQQL40PY`)

- Update underlying model from Claude Sonnet 4 to Claude Haiku 4.5
- More robust RAG lambda with improved error handling and tests (#29)
- Deprioritize publication RAG early in conversations; default to base SPARQL graph queries first and reserve SPARQL+Text for deeper exploration later in the thread (#24)
- Instruction update to address user-controlled navigation (#23, via #30)

Previous alias: `3AOKWTCUHH`
