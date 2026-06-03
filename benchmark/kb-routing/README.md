# KB Routing Benchmark

Evaluates whether the NF Portal multi-source Bedrock Agent selects the correct knowledge source for each query type. See [issue #36](https://github.com/nf-osi/portal-chatbot/issues/36).

## Background

The agent has two knowledge sources:

| Source | Label | Description | Detection |
|--------|-------|-------------|-----------|
| NF Help Docs KB | `DOCS` | Bedrock KB built from help.nf.synapse.org | `KNOWLEDGE_BASE` trace event or `WEB` citation |
| NF-OSI Knowledge Graph | `GRAPH` | Structured RDF graph via SPARQL action groups | `ACTION_GROUP` trace event |

This benchmark tests whether the agent routes queries to the right source — an issue the general-help eval cannot measure because it runs each question in isolation against a single-source agent.

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

`evaluate_kb_routing.py` invokes the agent, captures Bedrock trace events to detect which sources were used, and scores KB source selection accuracy alongside answer quality.

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

| Score | Meaning |
|-------|---------|
| 2 | Correct — all expected sources used (extras acceptable); or `NONE` and no sources used |
| 1 | Partial — some but not all expected sources used |
| 0 | Wrong — used wrong/no source when one was expected; or used any source when `NONE` expected |
| -1 | No trace detected (excluded from accuracy) |

### Answer quality scoring (LLM judge)

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
| KB selection accuracy | % turns where correct source(s) used (score ≥ 2) |
| Per-source accuracy | Accuracy broken down by DOCS / GRAPH / BOTH |
| Actual usage distribution | What sources the agent actually used |
| Answer quality | % turns scored 2 by the judge |
| Per-persona KB accuracy | Accuracy by CONTRIBUTOR, REUSER, FUNDER, etc. |
| Turn-1 vs turn-2+ accuracy | Whether prior session context affects routing |
