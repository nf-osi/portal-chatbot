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

`evaluate_bedrock_agent.py` invokes the deployed Bedrock Agent with each benchmark question (one fresh session per question), then uses an LLM judge to score how well the agent's free-text response corresponds to the known correct answer. Although the dataset is multiple-choice, evaluation is done in free-response format to better reflect real-world agent interaction.

### Requirements

```bash
pip install boto3 pandas
```

You also need AWS credentials with access to the Bedrock Agent and Bedrock Runtime (for the judge model). The script creates a `boto3.Session` using the `--profile` flag, which resolves credentials in the standard boto3 order:

1. **Named profile** (`--profile my-profile`) — reads from `~/.aws/credentials` and `~/.aws/config`.
2. **Environment variables** — if using the default profile, you can set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN` for temporary credentials (e.g. from `aws sso login` or `aws sts assume-role`).
3. **Instance/container role** — if running on EC2, ECS, or Lambda, boto3 picks up the attached IAM role automatically.

### Run

```bash
cd benchmark/general-help
python evaluate_bedrock_agent.py
```

All options have sensible defaults. Override any of them as needed:

```bash
python evaluate_bedrock_agent.py \
  --agent-id 2COISTBHRB \              # Bedrock Agent ID
  --alias-id TSTALIASID \              # Bedrock Agent alias ID
  --profile default \                  # AWS profile from ~/.aws/credentials
  --region us-east-1 \                 # AWS region
  --dataset help_qa_dataset_anthropic.json \  # benchmark dataset
  --output eval_results.json           # base output path (datestamp appended)
  # --judge-model can be used to override the LLM judge (defaults to Haiku 4.5)
```

| Flag | Default | Description |
|---|---|---|
| `--agent-id` | `2COISTBHRB` | Bedrock Agent ID |
| `--alias-id` | `TSTALIASID` | Bedrock Agent alias ID |
| `--profile` | `default` | AWS profile from `~/.aws/credentials` |
| `--region` | `us-east-1` | AWS region |
| `--dataset` | `help_qa_dataset_anthropic.json` | Path to benchmark dataset JSON |
| `--judge-model` | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | Bedrock model ID for the LLM judge |
| `--output` | `eval_results.json` | Base output path (a UTC datestamp is appended automatically) |

### Judge scoring

The LLM judge receives the question, the correct answer, and the agent's response, then assigns a score:

| Score | Meaning |
|---|---|
| 2 | Correct — clearly corresponds to the correct answer |
| 1 | Partially correct or vague |
| 0 | Incorrect or contradicts the correct answer |
| -1 | Judge failed to return a valid score |

### Output

Results are saved as `eval_results_<timestamp>.json` (e.g. `eval_results_20260421T153012Z.json`) so that successive runs can be compared for trend tracking. Each file contains:

- `timestamp` — UTC timestamp of the run
- `config` — agent ID, alias, judge model, and dataset used
- `results` — per-question scores, agent responses, cited URLs, and attribution hits
- `errors` — any questions that failed during invocation

### Metrics

The script prints the following metrics to stdout:

| Metric | Description |
|---|---|
| Overall accuracy | % of questions scored 2 (correct) by the judge |
| Score distribution | Count of 0 / 1 / 2 / judge-failed responses |
| Per-persona accuracy | Accuracy broken down by CONTRIBUTOR, REUSER, FUNDER, PATIENT, X |
| Cross-page vs single-page accuracy | Accuracy for questions sourced from one page vs. multiple pages |
| Source attribution rate | % of questions where the agent cited an expected source URL |

### References

- [AWS Bedrock Agent Runtime — `invoke_agent`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime/client/invoke_agent.html)
- [boto3 Bedrock Agent Runtime client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime.html)
- [LLM-as-a-Judge (Zheng et al., 2023)](https://arxiv.org/abs/2306.05685) — methodology for using an LLM to score free-text responses
