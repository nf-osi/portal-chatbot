# Agent Registrations

This directory contains configurations for different versions of NF Portal chatbot agents registered on Synapse.

## Current Registered Agents

| Agent Name | Status | Agent ID | Alias ID | Registration ID | Registered By | Synapse Link | Configuration | Notes |
|------------|--------|----------|----------|-----------------|---------------|--------------|---------------|-------|
| **nf-portal-pilot** | Development | `WU3QRWA0FQ` | `B0GQQL40PY` | `247` | `nf-service` | [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=247) | [nf-portal-pilot/](nf-portal-pilot/) | Amelia release |
| **nf-portal-chatbot** | Legacy | `2COISTBHRB` | `TSTALIASID` | `197` | `allaway` | [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=197) | [nf-portal-chatbot](https://github.com/Sage-Bionetworks/portal-agent-contexts/tree/main/nf-portal-chatbot) | Hackathon 2025/2026 version |
| **nf-portal-pilot** | Staging | `WU3QRWA0FQ` | `TSTALIASID` | `248` | `nf-service` | [Chat](https://www.synapse.org/Chat:initialMessage=hello&agentRegistrationId=248) | [nf-portal-pilot/](nf-portal-pilot/) | Latest/test version |
| **v0** | Legacy | `JRQZHX4RCC` | `TSTALIASID` | `11` | `allaway` | - | `v0/nf-chatbot-cloudformation.yml` | Legacy version |

## Compare and Contrast

### Evolution of Capabilities

| Feature | v0 (Legacy) | nf-portal-chatbot (Current) | nf-portal-pilot (Next) |
|---------|-------------|----------------------------|------------------------|
| **Primary Function** | Chat only | Portal help and navigation | Advanced search and discovery |
| **Data Source** | Static instructions only | Help docs | Knowledge graph + publications |
| **Query Capabilities** | None | Help docs | SPARQL + SPARQL+Text queries |
| **Response Format** | Plain text | Structured XML with actions | Structured XML with actions |
| **Navigation** | Text directions only | Direct redirects to portal pages | Direct redirects to portal pages |
| **Discovery** | ❌ No | ⚠️ Limited | ✅ Better (datasets, studies, tools) |
| **Publication Search** | ❌ No | ❌ No | ✅ Yes (indexed text search) |
| **Guided Prompts** | ❌ No | ✅ Yes (interactive suggestions) | ✅ Yes (interactive suggestions) |
| **Model** | Claude 3.5 Sonnet | Claude Sonnet 4 | Claude Haiku 4.5 |

### Key Differences

**v0** was an initial test deployment of the Synapse Custom Agent framework with no customizations beyond the system instructions. 
It had no ability to query data or access real-time information.

**nf-portal-chatbot** represents the production version focused on helping users with portal documentation and navigation.
- **Contextual Navigation**: Can redirect users directly to filtered views and detail pages
- **Interactive Guidance**: Provides contextual follow-up suggestions throughout the conversation

**nf-portal-pilot** is an experimental next-generation agent that adds:
- **Knowledge Graph Integration**: Direct SPARQL queries to the NF-OSI knowledge graph
- **Advanced Discovery**: Helps researchers discover linked datasets, publications, and tools more effectively
- **Publication Search**: Searches indexed publication text with citation attribution

Releases are named after famous pilots and explorers. Current release: **Amelia**. See [CHANGELOG](CHANGELOG.md) for history.

## Setup

To learn more about the Synapse Custom Agent framework, refer to [this internal Confluence doc](https://sagebionetworks.jira.com/wiki/spaces/PLFM/pages/3711303683/Adding+Custom+Agents+to+Synapse).
