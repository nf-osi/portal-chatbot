---
title: Source routing
description: Testing whether the agent queries the correct knowledge source. Only relevant if your agent has more than one source.
---

:::note
This benchmark only applies if your agent has **more than one** knowledge source (e.g. a docs KB plus a knowledge graph). If you only have a single docs KB, [grounded retrieval](/grounded-retrieval/) is the eval you need — skip this page.
:::

## What this tests

Source routing tests whether the agent consults the **correct** knowledge source for a given question — not whether the answer is correct. The best instructions in the world won't help if the agent queries the wrong source (or an unnecessary extra one), so this benchmark is how you validate and iterate on the routing rules in your system prompt.

The NF Portal Copilot has two sources — a documentation KB and a SPARQL-backed knowledge graph — so it needs this eval in addition to [grounded retrieval](/grounded-retrieval/) on each source individually. The **kb-routing benchmark** (`benchmark/kb-routing/`) covers this.

## How the dataset is built

`kb_routing_dataset.json` is a curated set of multi-turn sessions, each turn labeled with the source it should trigger:

| `expected` value | Meaning |
|---|---|
| `DOCS` | Documentation KB (process, policy, how-tos) |
| `GRAPH` | SPARQL action groups (counts, lists, specific records) |
| `BOTH` | Either source is acceptable, or both are needed for a compound question |
| `REDIRECT` | A navigation redirect, no KB lookup needed |
| `NONE` | No lookup expected — general knowledge or decline |

Sessions cover each source individually, mixed-source conversations where the user pivots between question types, compound questions needing multiple sources, and off-topic questions that shouldn't trigger any lookup.

## Example from a real run

Drawn from a 38-turn run (`routing_eval_results_20260626T181035Z.json`). Overall routing accuracy that run: **36/38 (95%)**.

A single session pivoting between sources — this is exactly the case this benchmark exists to catch:

**Turn 1** — "How long is the standard data embargo period on the portal?" (expected: `DOCS`)

> "The standard data embargo period on the NF Portal is **12-18 months**, though this can vary by funder..."

Routed to `DOCS`. Score: **2/2** (correct and efficient).

**Turn 2**, same session — "How many studies have released data?" (expected: `GRAPH`)

> "**87 studies** on the NF Portal have released data (with 'Available' status)..."

Routed to `GRAPH`. Score: **2/2**. The agent correctly re-routed mid-session from a policy question to a live-data-count question, rather than sticking with whichever source it used for turn 1 — the failure mode this benchmark is designed to surface.

## Scoring

Unlike grounded retrieval, there's no gold answer text to compare against — the primary signal comes from Bedrock trace events (`KNOWLEDGE_BASE` vs `ACTION_GROUP` invocations), not the response text:

| Score | Meaning |
|---|---|
| 2 | Correct and efficient — used exactly the expected source(s) |
| 1 | Correct but over-queried — right source plus unnecessary extras |
| 0 | Wrong source, or any source used when `NONE` expected |
| -1 | No trace detected (excluded from accuracy) |

## Running it

```bash
cd benchmark/kb-routing
python evaluate_kb_routing.py                          # routing only
python evaluate_kb_routing.py --judge                  # also score answer quality via LLM judge
```

See `benchmark/kb-routing/README.md` for the full dataset schema, detection method, and all CLI flags.
