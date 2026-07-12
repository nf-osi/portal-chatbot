---
name: redteam-eval
description: Run the NF Portal copilot adversarial redteam experiment and refresh docs/red-team-latest-report.md (use when user indicates updated report needed, such as upon changes to the benchmark, or agent's model or instructions)
---

You rerun `benchmark/redteam/evaluate_redteam.py` against the live dev Bedrock agent and refresh the aggregate report at `docs/red-team-latest-report.md`. This is a **live adversarial test against a real Bedrock Agent** — confirm scope with the user before running (which vulnerabilities, how many runs, which models) since each run takes ~15-25 min and makes real Bedrock calls.

## Background

Read `benchmark/redteam/README.md` for the full harness design and `benchmark/redteam/REPORT.md` for the baseline run's findings and known limitations. In short: an attacker LLM crafts adversarial messages against the dev agent (`ERAAPKTD4Q` / `TSTALIASID`), a judge LLM scores whether each attack succeeded, and results are saved to `benchmark/redteam/redteam_eval_results_<timestamp>.json`. **Never target the prod agent id (`R7WZ38JGKX`)** — the harness itself refuses this without `--allow-prod`.

## Known environment gotcha

`AWS_BEARER_TOKEN_BEDROCK` (used by Claude Code itself for its own model calls) will be present in the shell env and silently overrides SigV4 credentials for boto3's `invoke_model`/`invoke_agent`, causing `AccessDeniedException: Authentication failed`. **Unset it for the run:**

```bash
cd benchmark/redteam
env -u AWS_BEARER_TOKEN_BEDROCK python3 evaluate_redteam.py [flags]
```

If a run comes back with every case showing `NO VERDICT [degraded]: NO_TURNS_COMPLETED: ... AccessDeniedException`, that's this issue — delete the bad output file and rerun with the env var unset.

## Protocol

1. **Confirm scope with the user**: which vulnerability item(s) (default: all), how many runs, and which attacker/judge model pairing(s). The existing baseline used `us.anthropic.claude-sonnet-5` for both roles; varying models across runs (e.g. pairing `us.anthropic.claude-opus-4-8` against `us.anthropic.claude-sonnet-5` in both directions) reduces correlated-blind-spot risk — see REPORT.md Limitations. Check available Bedrock model/inference-profile ids in this account before assuming a model id works:
   ```bash
   env -u AWS_BEARER_TOKEN_BEDROCK aws bedrock list-inference-profiles --region us-east-1 \
     --query 'inferenceProfileSummaries[].inferenceProfileId' --output text
   ```

2. **Run the eval** (one invocation per attacker/judge pairing), from `benchmark/redteam/`:
   ```bash
   env -u AWS_BEARER_TOKEN_BEDROCK python3 evaluate_redteam.py \
     --attacker-model <id> --judge-model <id>
   ```
   Add `--vulnerability <id>` to scope to one item. Each full-suite run (~27 cases) takes roughly 15-25 minutes — run in the background and keep working while it completes. Do NOT run more than one against the same session concurrently is fine (independent sessions), but be mindful of Bedrock rate limits if launching many in parallel.

3. **Keep every output file.** Never delete a `redteam_eval_results_*.json` — the aggregate script and the variance analysis in the report depend on the full history. If a run fails/degrades (see gotcha above), delete only that bad file before retrying.

4. **Aggregate all runs**:
   ```bash
   cd benchmark/redteam
   python3 aggregate_redteam.py
   ```
   This combines every `redteam_eval_results_*.json` in the directory into per-vulnerability/category/technique success rates with mean + std-dev across runs (not just one run's point estimate), and writes `redteam_aggregate_results.json`.

5. **Review the successful-attack transcripts** in each new result file (`results[].attack_succeeded == true`) before writing anything up — read the actual `turns` transcript and judge `reason`, don't just report the rate.

6. **Rewrite `docs/red-team-latest-report.md`** from the aggregate output plus your review of any successful attacks. Structure it like `benchmark/redteam/REPORT.md` but reflecting the full multi-run picture:
   - Headline aggregate attack success rate (mean ± std across runs), not a single run's number.
   - Table of runs included (timestamp, attacker model, judge model, n cases).
   - Per-vulnerability / per-category / per-technique breakdown with mean/std and pooled counts.
   - Full detail on every distinct successful attack found across all runs (dedupe if the same failure mode recurs across runs — note recurrence as a signal of a stable weakness rather than a fluke).
   - Carry forward or update the Limitations section — note if this run round changed model diversity, added runs, etc.
   - Suggested mitigations for anything that recurred across runs (recurring = worth a prompt/instruction change; a single-run one-off is weaker evidence per the Limitations discussion in REPORT.md).

7. **Do not commit** unless the user asks — surface the new result files, the updated `docs/red-team-latest-report.md`, and a summary of what changed, and let the user decide.

## Reference files

- `benchmark/redteam/evaluate_redteam.py` — the harness
- `benchmark/redteam/aggregate_redteam.py` — cross-run aggregation
- `benchmark/redteam/redteam_config.json` — vulnerability items being tested
- `benchmark/redteam/README.md` — full design doc, technique taxonomy, flags
- `benchmark/redteam/REPORT.md` — original single-run baseline report and limitations
- `docs/red-team-latest-report.md` — the aggregate report this skill maintains
