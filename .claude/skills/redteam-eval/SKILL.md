---
name: redteam-eval
description: Run the NF Portal copilot adversarial redteam experiment and refresh docs/content/docs/benchmarking-and-evaluation/red-team-report.md (use when user indicates updated report needed, such as upon changes to the benchmark, or agent's model or instructions)
---

You run `benchmark/redteam/evaluate_redteam.py` against the live dev Bedrock agent and refresh the aggregate report at `docs/content/docs/benchmarking-and-evaluation/red-team-report.md`. This is a **live adversarial test against a real Bedrock Agent** — confirm scope with the user before running (which vulnerabilities, how many runs, which models) since each run takes ~15-25 min and makes real Bedrock calls.

## Background

Read `benchmark/redteam/README.md` for the full harness design and any previous artifacts such as `docs/content/docs/benchmarking-and-evaluation/red-team-report.md` for the last run's findings and known limitations. In short: an attacker LLM crafts adversarial messages against the dev agent (`ERAAPKTD4Q` / `TSTALIASID`), a judge LLM scores whether each attack succeeded, and results are saved to `benchmark/redteam/redteam_eval_results_<timestamp>.json`. **Never target the prod agent id (`R7WZ38JGKX`)** — the harness itself refuses this without `--allow-prod`.

## Known environment gotcha

`AWS_BEARER_TOKEN_BEDROCK` (used by Claude Code itself for its own model calls) will be present in the shell env and silently overrides SigV4 credentials for boto3's `invoke_model`/`invoke_agent`, causing `AccessDeniedException: Authentication failed`. **Unset it for the run:**

```bash
cd benchmark/redteam
env -u AWS_BEARER_TOKEN_BEDROCK python3 evaluate_redteam.py [flags]
```

If a run comes back with every case showing `NO VERDICT [degraded]: NO_TURNS_COMPLETED: ... AccessDeniedException`, that's this issue — delete the bad output file and rerun with the env var unset.

## Protocol

1. **Confirm scope with the user**: full run or selected vulnerability item(s) to augment data only (default: all), how many runs, which attacker/judge model pairing(s). The existing baseline used `us.anthropic.claude-sonnet-5` for both roles; varying models across runs (e.g. pairing `us.anthropic.claude-opus-4-8` against `us.anthropic.claude-sonnet-5` in both directions) reduces correlated-blind-spot risk. Check available Bedrock model/inference-profile ids in this account before assuming a model id works:
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

6. **Revise `docs/content/docs/benchmarking-and-evaluation/red-team-report.md`** from the new aggregate output plus your review of any successful attacks. Expected structure:
   - Title: `# NF Portal Copilot Red Team — Latest Report`
   - Background section: Context about the scope and purpose of the redteam eval, which **can stay the same** unless user specifies updates needed.
   - Methodology section: Concise summary explaining vulnerability and attack taxonomy covered, table of runs included (timestamp, attacker model, judge model, n cases), reference to relevant scripts. 
   - Results section: Headline aggregate attack success rate (mean ± std across runs), per-vulnerability / per-category / per-technique breakdown with mean/std and pooled counts. Full detail on every distinct successful attack found across all runs (dedupe if the same failure mode recurs across runs, analyze whether recurrence is a consistent weakness or chance).
   - Discussion section: Highlight and offer reasoning for most pertinent results, summarize overall risk, suggest mitigations/solutions, note limitations, and optionally propose experiment enhancements to implement.

7. **Do not commit** unless the user asks — surface the new result files, the updated `docs/content/docs/benchmarking-and-evaluation/red-team-report.md`, a summary of what changed, and let the user review and edit.

## Reference files

- `benchmark/redteam/evaluate_redteam.py` — the harness
- `benchmark/redteam/aggregate_redteam.py` — cross-run aggregation
- `benchmark/redteam/redteam_config.json` — vulnerability items being tested
- `benchmark/redteam/README.md` — full design doc, technique taxonomy, flags
- `docs/content/docs/benchmarking-and-evaluation/red-team-report.md` — the latest aggregate report this skill maintains
