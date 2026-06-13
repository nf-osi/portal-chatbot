# Agent Registrations

This directory contains configurations for NF Portal agents registered on Synapse.

## Stacks

The Copilot is deployed as two CloudFormation stacks from the same template (`nf-portal-copilot/cloudformation.yaml`):

- **nf-portal-copilot-prod** — Production. Stable version that portal users interact with. Agent `R7WZ38JGKX`, alias `XBZHRAX5JH`.
- **nf-portal-copilot-legacy** (deleted) — Pre-CloudFormation agent. Agent `WU3QRWA0FQ`, alias `B0GQQL40PY`.
- **nf-portal-copilot-dev** — Development/staging. Used to test instruction changes, model swaps, and Lambda updates before promoting to prod. Agent `ERAAPKTD4Q`, alias `RPL5MEHCFU`.

## Synapse Registrations

Only user-facing (prod) agents are registered with Synapse. Dev agents are tested internally.

- **nf-portal-copilot** — Registration `247` by `nf-service` — [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=247). Amelia release.
- **nf-portal-chatbot** (legacy) — Registration `197` by `allaway` — [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=197). Hackathon 2025/2026 version. Config in [portal-agent-contexts](https://github.com/Sage-Bionetworks/portal-agent-contexts/tree/main/nf-portal-chatbot).
- **v0** (legacy) — Registration `11` by `allaway`. Original test deployment.

## Copilot Capabilities

- **Knowledge Graph Integration**: SPARQL queries against the NF-OSI knowledge graph
- **Publication Search**: Indexed text search with citation attribution
- **Portal Navigation**: Redirects users to filtered Explore pages (datasets, studies, tools, etc.)
- **Guided Prompts**: Interactive follow-up suggestions

Releases are named after famous pilots and explorers. Current release: **Amelia**. See [CHANGELOG](CHANGELOG.md) for history.

## CI/CD

Changes under `agents/nf-portal-copilot/` trigger the `deploy-copilot` workflow (`.github/workflows/deploy-copilot.yml`):

- **Manual dispatch** (`workflow_dispatch`) — deploys to the dev stack for testing. Trigger from any branch via the Actions UI or `gh workflow run deploy-copilot.yml --ref my-branch`.
- **Merge to main** — automatically deploys to the prod stack.

The workflow detects what changed and only runs the needed steps:

- Lambda code only → uploads zip to S3 and updates the function in-place (no stack update)
- Template/instructions/schema → runs `cloudformation deploy` on the stack

AWS credentials use GitHub OIDC via the `GitHubActionsNFPortalChatbot` IAM role, stored as the `AWS_OIDC_ROLE_ARN` repo secret.

## Setup

To learn more about the Synapse Custom Agent framework, refer to [this internal Confluence doc](https://sagebionetworks.jira.com/wiki/spaces/PLFM/pages/3711303683/Adding+Custom+Agents+to+Synapse).
