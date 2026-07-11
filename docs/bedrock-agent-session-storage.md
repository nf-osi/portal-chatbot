---
title: Bedrock Agent Session Storage For Clients
description: Implementation note for staging and production client teams on Bedrock agent session storage.
---

This document is the implementation note for the staging and production client teams.

## Why this exists

In testing, classic Amazon Bedrock Agents did **not** automatically expose `InvokeAgent` conversation history through:

- `ListInvocations`
- `ListInvocationSteps`
- `GetInvocationStep`

Even when we:

1. created a Bedrock session with `CreateSession`
2. reused that returned UUID as the `sessionId` for `InvokeAgent`

the session resource became retrievable, but the agent turn did **not** appear in invocation history.

## Recommended pattern

The client should treat Bedrock Session Management as an **application-managed store** around `InvokeAgent`.

For each user turn:

1. Create or reuse a Bedrock session resource.
2. Call `InvokeAgent` with the same session ID.
3. Create one invocation for that user turn.
4. Store the user prompt as an invocation step.
5. Store the agent response as an invocation step.
6. Optionally store trace output as an additional invocation step.

This gives you retrievable Bedrock-native history through:

- `ListSessions`
- `GetSession`
- `ListInvocations`
- `ListInvocationSteps`
- `GetInvocationStep`

## Example script

Use [scripts/store_bedrock_agent_session_turn.py](/home/avu/sage/nf/portal-chatbot/scripts/store_bedrock_agent_session_turn.py) as the reference implementation.

The script does the full sequence:

- `CreateSession` when no session ID is supplied
- `InvokeAgent`
- `CreateInvocation`
- `PutInvocationStep` for the user prompt
- `PutInvocationStep` for the agent response
- optional `PutInvocationStep` for trace payloads

Example:

```bash
python3 scripts/store_bedrock_agent_session_turn.py \
  --prompt "hello" \
  --enable-trace \
  --store-trace-step
```

To continue an existing conversation:

```bash
python3 scripts/store_bedrock_agent_session_turn.py \
  --session-id 65a03dc7-a29c-49c2-ae30-041dbb418fd9 \
  --prompt "show me MPNST datasets"
```

## Integration guidance

The client team should not shell out to this script in production. Instead, copy the sequence into the application code.

Recommended mapping:

- one Bedrock session resource per client conversation thread
- one invocation per user turn
- one step for the user message
- one step for the agent response
- one optional step for trace or debugging metadata

Suggested session metadata:

- environment
- agent alias ID
- application name
- user or tenant identifier if allowed by policy
- source channel such as `staging-web` or `prod-web`

Suggested invocation description:

- short human-readable summary of the turn, such as the route, feature, or prompt class

## Retrieval model

Later, analysis or support tooling can reconstruct the stored conversation by:

1. listing sessions
2. listing invocations for one session
3. listing steps for one invocation
4. fetching step payloads

The important distinction is:

- `InvokeAgent` preserves agent context using `sessionId`
- the client must still persist retrievable turn history explicitly using invocation APIs

## Known limitations

- This pattern stores what the client writes. It is not a raw Bedrock transcript export.
- If the client omits `CreateInvocation` and `PutInvocationStep`, the turn may not appear in retrievable session history.
- Trace payloads can be verbose. Store them only when needed, or gate them by environment.
