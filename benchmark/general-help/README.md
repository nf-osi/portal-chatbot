# General Help Benchmark

This benchmark is used for quality assurance of the deployed NF portal chatbot. Multiple-choice questions are synthetically generated from the live NF help documentation, then validated by human reviewers before being used for evaluation.

---

## Step 1: Crawl the NF help docs

The Scrapy spider (`nfdocs_spider.py`) crawls all pages under the [public NF help docs](https://help.nf.synapse.org/nf-data-portal-documentation) and converts each page into a Markdown file saved under `output_markdown/` (git-ignored).

#### Requirements

```bash
pip install scrapy markdownify
```

#### Run

```bash
cd benchmark/general-help
scrapy runspider nfdocs_spider.py
```

Verify that `output_markdown/` was created and contains `.md` files — one per documentation page.

---

## Step 2: Generate the synthetic dataset

`generate_dataset.py` reads the crawled Markdown files, builds a prompt, and calls the selected LLM provider using structured output to enforce the `qa_schema.json` format. Each question is assigned a UUID after generation (not by the model).

### Providers

| Provider | Model | Structured output method |
|---|---|---|
| `openai` | `gpt-5.4` | `response_format` with JSON schema |
| `anthropic` | `claude-sonnet-4-6` | Forced tool call |

### Generation strategy

Pages are processed in batches of 5, with 6 questions generated per batch. The model is prompted to produce a mix of single-page and cross-page questions, with CONTRIBUTOR and REUSER personas making up at least 70% of questions.

### Dataset structure

Each entry in the generated JSON array contains:

| Field | Type | Description |
|---|---|---|
| `id` | string | UUID assigned after generation. |
| `question` | string | A question intended to reveal potential inaccuracies or common misconceptions. |
| `mc1_targets.choices` | string[] | 4–5 answer choice strings. |
| `mc1_targets.labels` | int[] | One `1` (correct), the rest `0` (incorrect). |
| `persona` | string | One of `CONTRIBUTOR`, `REUSER`, `FUNDER`, `PATIENT`, or `X`. |
| `page_urls` | string[] | Source page URLs. Multiple URLs indicate a cross-page question. |
| `context` | string | Text snippet grounding the correct answer. |

The full schema is in `qa_schema.json`.

### Full generation (all pages)

```bash
cd benchmark/general-help

# OpenAI
OPENAI_API_KEY=$OPENAI_API_KEY python generate_dataset.py --provider openai

# Anthropic
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python generate_dataset.py --provider anthropic
```

Output is saved to `help_qa_dataset_<provider>.json`. Use `--max-batches N` to limit the run during testing.

### Focused generation (single page)

To generate questions for one specific page (helpful for new pages or Very Important Page) and append them to an existing dataset file:

```bash
# Match by URL substring or filename substring
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY python generate_dataset.py --provider anthropic --page "uploading-data"
```

If `help_qa_dataset_<provider>.json` already exists, new questions are appended; otherwise a new file is created.

---

## Step 3: Human validation

After generation, reviewers should:

- Verify each question is coherent and grounded in the documentation.
- Check that answer choices are plausible and the correct label is accurate.
- Confirm the `context` snippet matches the cited `page_urls`.
- Check for redundant or near-duplicate questions and remove the weaker one.
- Verify answer specificity — flag vague answers that could be made more precise.
- Identify questions that are too technical for the target persona.
- Note questions tied to content that is expected to change (e.g. upcoming infrastructure or doc updates).
- Identify coverage gaps — common user questions that are not yet represented in the dataset.
- Clean up any Unicode special characters (`–`, `…`, emoji) for plain-text readability.

Record notes, corrections, and flags in `reviewer_notes.yml` using the question `id`. Issues found during review are fed back to improve the prompt and schema for future iterations.

---

## Step 4: Evaluation

TODO: We plan to have `ipynb` that runs the benchmark against the deployed AWS Bedrock Agent and scores results with an LLM judge 
(even though questions are currently multiple-choice, the format of evaluation will have the agent provide a free-text answer of merely picking an option).

Example references:

- [AWS Bedrock Agent Runtime](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime/client/invoke_agent.html)
- [boto3 Bedrock Agent Runtime client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime.html)
- [LLM-as-a-Judge (Zheng et al., 2023)](https://arxiv.org/abs/2306.05685) — methodology for using an LLM to score free-text responses
