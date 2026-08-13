---
title: Grounded retrieval
weight: 20
---

# Grounded retrieval

## What this tests

Grounded retrieval evaluates a single knowledge source in isolation: given a question with a known correct answer, does the agent retrieve the right document and produce an answer consistent with it? This is the baseline eval every portal copilot needs — any agent with at least one docs knowledge base should have one of these, even before adding [source routing](/docs/benchmarking-and-evaluation/source-routing/) for multi-source setups.

The NF Portal Copilot's version of this is the **general-help benchmark** (`benchmark/general-help/`), which evaluates the docs KB built from help.nf.synapse.org.

## How the dataset is built

Questions are generated synthetically from the live help docs, then validated by human reviewers before use:

1. **Crawl** — a Scrapy spider converts each help doc page into Markdown.
2. **Generate** — an LLM (OpenAI or Anthropic, with structured output) reads the crawled pages and produces multiple-choice questions, each with 4-5 answer choices, one correct label, a target persona (`CONTRIBUTOR`, `REUSER`, `FUNDER`, `PATIENT`, or `X`), the source page URL(s), and a `context` snippet grounding the correct answer.
3. **Validate** — human reviewers check coherence, answer specificity, and whether the question is scoped appropriately for its persona.

A dataset entry looks like:

```json
{
  "question": "What is the default license applied to non-human data submitted to the NF Data Portal?",
  "mc1_targets": {
    "choices": ["CC BY 4.0 (Attribution)", "CC0 (No Rights Reserved)", "CC BY-SA (Attribution-ShareAlike)", "All Rights Reserved"],
    "labels": [0, 1, 0, 0]
  },
  "persona": "CONTRIBUTOR",
  "page_urls": ["https://help.nf.synapse.org/nf-data-portal-documentation/contributing-data/about-data-licensing"],
  "context": "As a data contributor, you will select the license that applies to your data. The default option for non-human data is CC0..."
}
```

Although the dataset is multiple-choice, evaluation runs in **free-response** format — the agent is asked the plain question, not shown the answer choices — to better reflect how a real user interacts with the copilot. An LLM judge then scores the free-text response against the known correct answer.

## Examples from a real run

Drawn from a 50-question run (`eval_results_20260514T223326Z.json`) against the docs KB agent. Overall accuracy that run: **40/50 (80%)**, with correct source attribution on 40/50 answers.

### Grounded and correct

**Question:** "What is the default license applied to non-human data submitted to the NF Data Portal?"

The agent cited the expected page and gave the correct answer:

> "The default license applied to non-human data submitted to the NF Data Portal is CC0 (Creative Commons Zero). This is described as a 'no rights reserved' license by Creative Commons... Data contributors can select the license that applies to their data during submission, with CC0 being the default option specifically for non-human data."

Judge score: **2/2** (correct). Cited URL matched the expected source exactly.

### Honest gap instead of a hallucination

**Question:** "What is the maximum file download size supported through the Synapse web interface?" (expected answer: "5 GB or 100 files")

The agent found nothing relevant in the KB and said so, rather than guessing:

> "I apologize, but I wasn't able to find specific information about the maximum file download size supported through the Synapse web interface in the available documentation... I recommend: 1. Checking the official Synapse documentation... 2. Contacting Synapse support directly..."

Judge score: **0/2** (incorrect — the answer wasn't retrieved). This scores as a failure, but it's the failure mode you want: no citation, no invented number, an honest "I don't have this" plus a pointer elsewhere. The alternative — a confident wrong number — would be a groundedness failure, not just a coverage gap. This kind of miss usually means either the content isn't in the crawled docs, or it's there but wasn't retrieved for this query — worth checking both when triaging misses.

## Running it

```bash
cd benchmark/general-help
python evaluate_bedrock_agent.py
```

See `benchmark/general-help/README.md` for dataset generation (`generate_dataset.py`), the full scoring rubric, all CLI flags, and metrics reported (overall accuracy, per-persona accuracy, cross-page vs single-page accuracy, source attribution rate).
