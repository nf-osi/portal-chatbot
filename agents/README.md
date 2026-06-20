# Agent Registrations

This directory contains NF Portal agent configurations. Originally referred to as "chatbot" and renamed to "copilot" to better align with the product concept.

## Copilot Stacks

The Copilot is deployed as two CloudFormation stacks from the same template (`nf-portal-copilot/cloudformation.yaml`):

- **nf-portal-copilot-prod** — Production. Stable version that portal users interact with. Agent `R7WZ38JGKX`.
- **nf-portal-copilot-dev** — Development/staging. Used to test instruction changes, model swaps, and Lambda updates before promoting to prod. Agent `ERAAPKTD4Q`.

## Synapse Registrations

Currently, only user-facing (prod) agents are registered with Synapse. Dev agents are tested internally. This includes historical registrations:

- **nf-portal-copilot (Harriet)** — Registration `312` by `nf-service` — [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=312). Agent `R7WZ38JGKX`.
- **nf-portal-copilot (Amelia)** — Registration `247` by `nf-service` — [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=247).
- **nf-portal-chatbot (legacy)** — Registration `197` by `allaway` — [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=197). Hackathon version.
- **v0 (legacy)** — Registration `11` by `allaway`. Original test deployment.

## Copilot Capabilities

- **Help Docs QA**: Answers process, policy, and how-to questions from the NF Portal documentation
- **Knowledge Graph Integration**: SPARQL queries against the NF-OSI knowledge graph
- **Publication Search**: Indexed text search with citation attribution
- **Portal Navigation**: Redirects users to filtered Explore pages (datasets, studies, tools, etc.)
- **Guided Prompts**: Interactive follow-up suggestions

Major releases with significant changes are named after famous pilots and explorers. See [CHANGELOG](CHANGELOG.md) for history.

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
