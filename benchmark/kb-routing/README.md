# KB Routing Benchmark

Evaluates whether the NF Portal multi-source Bedrock Agent selects the correct knowledge source for each query type. See [issue #36](https://github.com/nf-osi/portal-chatbot/issues/36).

## Background

The agent has two knowledge sources:

| Source | Label | Description | Detection |
|--------|-------|-------------|-----------|
| NF Help Docs KB | `DOCS` | Bedrock KB built from help.nf.synapse.org | `KNOWLEDGE_BASE` trace event or `WEB` citation |
| NF-OSI Knowledge Graph | `GRAPH` | Structured RDF graph via SPARQL action groups | `ACTION_GROUP` trace event |

**This benchmark measures source routing, not answer correctness.** The primary metric is whether the agent consulted the right knowledge source — determined from Bedrock trace events — not whether the response text matches a gold answer. This is distinct from the general-help eval, which scores answer quality against known correct answers for a single-source agent. Answer quality is recorded here as a secondary metric only.

---

## Dataset

`kb_routing_dataset.json` — a curated set of multi-turn sessions, each labeled with the expected KB source per turn.

### Session structure

```json
{
  "session_id": "s-mixed-01",
  "session_type": "MIXED",
  "description": "Contributor asks about process, then pivots to data inventory",
  "n_turns": 2,
  "turns": [
    {
      "id": "s-mixed-01-t1",
      "question": "What is the data embargo policy?",
      "expected_kb": "DOCS",
      "persona": "CONTRIBUTOR",
      "notes": "Policy question answered by documentation."
    },
    {
      "id": "s-mixed-01-t2",
      "question": "Show me all publicly available datasets",
      "expected_kb": "GRAPH",
      "persona": "REUSER",
      "notes": "Data inventory requires querying the KG."
    }
  ]
}
```

### `expected_kb` values

| Value | Meaning |
|-------|---------|
| `DOCS` | Agent should use the documentation KB (process, policy, how-tos) |
| `GRAPH` | Agent should use SPARQL action groups (counts, lists, specific records) |
| `BOTH` | Either source is acceptable, or both should be used for a compound question |
| `NONE` | No KB lookup expected — agent should answer from general knowledge or decline |

### `session_type` values

| Value | Meaning |
|-------|---------|
| `DOCS` | All turns expect the documentation KB |
| `GRAPH` | All turns expect the KG / SPARQL action groups |
| `MIXED` | Turns route to different sources within the same session |
| `BOTH` | All turns accept either or both sources (compound or ambiguous questions) |
| `NONE` | No KB lookup expected for any turn |

### Dataset composition

| `session_type` | Sessions | Single-turn | Multi-turn | Turns |
|----------------|----------|-------------|------------|-------|
| DOCS | 5 | 3 | 2 | 8 |
| GRAPH | 5 | 3 | 2 | 8 |
| MIXED | 4 | — | 4 | 13 |
| BOTH | 2 | 1 | 1 | 3 |
| NONE | 3 | 2 | 1 | 4 |
| **Total** | **19** | **9** | **10** | **36** |

---

## Step 1: Expand the dataset

Add sessions directly to `kb_routing_dataset.json` following the schema in `kb_routing_schema.json`. Each session requires `session_id`, `session_type`, `description`, `n_turns` (must equal the length of `turns`), and turns with `id`, `question`, `expected_kb`, and `persona`.

---

## Step 2: Human validation

- Verify each `expected_kb` label is accurate for the question.
- Check that multi-turn sessions flow naturally (follow-up turns are coherent).
- Flag questions where either source gives a valid answer (change `expected_kb` to `BOTH`); this includes both compound questions and genuinely ambiguous queries.
- Ensure GRAPH questions can't be answered from docs alone.
- Ensure DOCS questions don't require live KG data.

---

## Step 3: Evaluate

`evaluate_kb_routing.py` invokes the agent and captures Bedrock trace events to determine which knowledge source was actually used. The primary output is KB source selection accuracy — whether the agent routed to the expected source — not whether the answer text is correct. Answer quality is scored as a secondary signal by an LLM judge.

### Execution flow

For each session the script:

1. Creates a fresh Bedrock `sessionId` (UUID)
2. Sends `turns` to the agent **in order**, reusing the same `sessionId` — so each turn arrives with the prior conversation in context
3. After each turn, inspects trace events and response citations to detect which KB source was used (`DOCS`, `GRAPH`, both, or neither), then scores it against `expected_kb`
4. Moves to the next turn in the same session before starting a new `sessionId` for the next session

Single-turn sessions run this loop once. The `n_turns` field exists so sessions can be pre-filtered by turn count before running the eval (e.g. to isolate the effect of prior context on routing decisions).

### Requirements

```bash
pip install boto3 pandas
```

AWS credentials with access to the Bedrock Agent and Bedrock Runtime.

### Run

```bash
cd benchmark/kb-routing
python evaluate_kb_routing.py
```

Override defaults as needed:

```bash
python evaluate_kb_routing.py \
  --agent-id WU3QRWA0FQ \
  --alias-id TSTALIASID \
  --profile default \
  --region us-east-1 \
  --dataset kb_routing_dataset.json \
  --output routing_eval_results.json
  # --judge-model to override LLM judge (defaults to Haiku 4.5)
```

| Flag | Default | Description |
|------|---------|-------------|
| `--agent-id` | `WU3QRWA0FQ` | Bedrock Agent ID |
| `--alias-id` | `TSTALIASID` | Bedrock Agent alias ID |
| `--profile` | `default` | AWS profile |
| `--region` | `us-east-1` | AWS region |
| `--dataset` | `kb_routing_dataset.json` | Sessions dataset |
| `--judge-model` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Answer quality judge |
| `--output` | `routing_eval_results.json` | Base output path (datestamp appended) |

### Detection method

The script enables `enableTrace=True` on agent invocations and inspects orchestration trace events:

- `invocationType: "KNOWLEDGE_BASE"` or `type: "KNOWLEDGE_BASE"` → `DOCS` used
- `invocationType: "ACTION_GROUP"` or `type: "ACTION_GROUP"` → `GRAPH` used
- `WEB`-type citation in response chunk → also marks `DOCS`

### KB selection scoring

| Score | Meaning | `kb_correct` |
|-------|---------|:---:|
| 2 | Correct and efficient — used exactly the expected source(s); or `NONE` and no sources used | ✓ |
| 1 | Correct but over-queried — used the right source plus unnecessary extras (`DOCS`/`GRAPH` turns only); or expected `BOTH` but only one source used | ✓ |
| 0 | Wrong — used no source or wrong source when one was expected; or used any source when `NONE` expected | ✗ |
| -1 | No trace detected (excluded from accuracy reporting) | — |

`kb_correct` (`score >= 1`) captures whether the agent reached the right source at all. `score == 2` additionally captures routing efficiency — useful for identifying unnecessary KB calls on single-source questions.

### Answer quality scoring (LLM judge, secondary)

Unlike the general-help eval, there is no gold answer to compare against. The judge scores whether the response is coherent and on-topic given what type of source should have been used — not whether it matches a known correct answer.

| Score | Meaning |
|-------|---------|
| 2 | Clear, on-topic, informative answer |
| 1 | Partial or vague |
| 0 | Off-topic, evasive, or error |
| -1 | Judge failure |

### Output

Results are saved as `routing_eval_results_<timestamp>.json`. Each file contains:

- `timestamp` — UTC timestamp
- `config` — agent ID, alias, judge model, dataset
- `results` — per-turn scores including `kb_used`, `kb_score`, `kb_correct`, `answer_score`
- `errors` — failed turns

### Metrics printed

| Metric | Description |
|--------|-------------|
| KB routing accuracy | % turns with `kb_correct` (score ≥ 1) — agent reached the right source |
| KB routing efficiency | % turns with score = 2 — right source used with no unnecessary extras |
| Over-query rate | % `DOCS`/`GRAPH` turns with score = 1 — right source used but extras consulted |
| Per-source breakdown | Above metrics broken down by `expected_kb` (DOCS / GRAPH / BOTH / NONE) |
| Actual usage distribution | What source combinations the agent actually used |
| Answer quality | % turns scored 2 by the LLM judge |
| Per-persona KB accuracy | Routing accuracy by CONTRIBUTOR, REUSER, FUNDER, etc. |
| Turn-1 vs turn-2+ accuracy | Whether prior session context affects routing decisions |
