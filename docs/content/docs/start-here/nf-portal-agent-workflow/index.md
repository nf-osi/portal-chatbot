---
title: Reference workflow
weight: 20
---

# Reference workflow

The NF Portal Copilot combines documentation and knowledge-graph sources behind a Bedrock agent, then iterates through evaluation before promoting changes from dev to prod.

![Diagram showing the NF Portal agent workflow: knowledge sources (Docs KB and Knowledge Graph) feed into a CloudFormation-managed agent stack (instructions, Lambda SPARQL adapter, agent, alias); the agent alias is evaluated, results decide whether to revise or promote; ready changes flow through CI/CD dev and prod stacks, ending in an update to the Synapse agent registration.](./diagrams/nf-portal-agent-workflow.svg)
