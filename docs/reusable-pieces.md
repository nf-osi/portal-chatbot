---
title: Reusable pieces
description: The Lambda function and CloudFormation template from the NF Portal Copilot that you can adapt for your own portal.
---

### Lambda function (only needed with a SPARQL endpoint)

`agents/nf-portal-copilot/lambda/nfGraphRag/lambda_function.py` is a thin adapter that exposes four SPARQL helper operations to the Bedrock Agent:

| Function | Purpose |
|---|---|
| `sparqlQuery` | Run arbitrary SPARQL, including SPARQL+Text for publication search |
| `getSchema` | List ontology classes and properties |
| `getShape` | SHACL constraints for a class |
| `countByType` | Quick RDF type inventory |

To reuse this for your portal:
- Point `SPARQL_ENDPOINT` at your own endpoint
- If your endpoint requires auth, set `SPARQL_AUTH_TOKEN`
- The OpenAPI schema (`openapi.yaml`) defines the action group interface and can be used as-is

### CloudFormation template

`agents/nf-portal-copilot/cloudformation.yaml` deploys the full stack: IAM roles, Lambda function, Bedrock Agent with action group, knowledge base attachment, and agent alias. See the usage comments at the top of the template for what to replace.

Key things to change for your portal:
- **`Instruction`** — the system prompt, embedded inline. Replace with your agent's instructions.
- **`KnowledgeBaseId`** — the NF docs KB ID is the default. Replace with your own or remove the block entirely.
- **`SparqlEndpoint`** — point at your SPARQL endpoint.
- **`FoundationModelId`** — defaults to Claude Haiku 4.5; change as needed.

Deploy with:

```bash
aws cloudformation deploy \
  --template-file agents/nf-portal-copilot/cloudformation.yaml \
  --stack-name my-portal-copilot-dev \
  --parameter-overrides \
      AgentName=my-portal-copilot-dev \
      SparqlEndpoint=https://my-endpoint/ \
      LambdaS3Bucket=my-bucket \
      LambdaS3Key=lambda/my-function.zip \
  --capabilities CAPABILITY_NAMED_IAM
```
