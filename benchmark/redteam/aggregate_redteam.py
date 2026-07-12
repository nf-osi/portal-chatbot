#!/usr/bin/env python3
"""Aggregate multiple redteam_eval_results_*.json runs into stable per-item,
per-category, and per-technique success rates with run-to-run variance.

A single run is a point estimate (see REPORT.md Limitations): attack
generation is stochastic and the judge is itself an LLM. This script combines
every timestamped result file in the directory (each typically a different
attacker/judge model pairing) so rates aren't eyeballed from one run alone.

Usage:
    python aggregate_redteam.py                     # all redteam_eval_results_*.json here
    python aggregate_redteam.py --glob 'redteam_eval_results_202607*.json'
    python aggregate_redteam.py --output aggregate.json
"""

import argparse
import json
from pathlib import Path

import pandas as pd


def load_runs(pattern: str, directory: Path) -> list[dict]:
    files = sorted(directory.glob(pattern))
    if not files:
        raise SystemExit(f"No result files matched {pattern!r} in {directory}")
    runs = []
    for f in files:
        with open(f) as fh:
            payload = json.load(fh)
        payload["_file"] = f.name
        runs.append(payload)
    return runs


def flatten(runs: list[dict]) -> pd.DataFrame:
    rows = []
    for run in runs:
        cfg = run["config"]
        run_label = f"{cfg['attacker_model']}→{cfg['judge_model']}"
        for r in run["results"]:
            rows.append({
                **r,
                "run_file": run["_file"],
                "run_timestamp": run["timestamp"],
                "attacker_model": cfg["attacker_model"],
                "judge_model": cfg["judge_model"],
                "run_label": run_label,
            })
    df = pd.DataFrame(rows)
    return df


def per_run_rate(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """For each (group_col value, run), the run's success rate within that
    group. Then mean/std of that rate ACROSS runs — this is the run-to-run
    variance the single-run report couldn't show."""
    scorable = df[df["passed"].notna()]
    per_run = (scorable.groupby([group_col, "run_timestamp"])["attack_succeeded"]
                        .mean()
                        .reset_index(name="run_rate"))
    agg = (per_run.groupby(group_col)["run_rate"]
                   .agg(mean_rate="mean", std_rate="std", n_runs="count")
                   .reset_index())
    # Pooled counts across all runs (total trials, total successes), for context.
    pooled = (scorable.groupby(group_col)["attack_succeeded"]
                       .agg(pooled_n="count", pooled_successes="sum")
                       .reset_index())
    out = agg.merge(pooled, on=group_col)
    out["std_rate"] = out["std_rate"].fillna(0.0)
    out["mean_rate"] = out["mean_rate"].map(lambda x: round(x, 4))
    out["std_rate"] = out["std_rate"].map(lambda x: round(x, 4))
    return out.sort_values("mean_rate", ascending=False)


def overall_rate(df: pd.DataFrame) -> dict:
    scorable = df[df["passed"].notna()]
    per_run = scorable.groupby("run_timestamp")["attack_succeeded"].mean()
    return {
        "n_runs": int(per_run.count()),
        "mean_rate": round(float(per_run.mean()), 4),
        "std_rate": round(float(per_run.std()) if per_run.count() > 1 else 0.0, 4),
        "pooled_n": int(len(scorable)),
        "pooled_successes": int(scorable["attack_succeeded"].sum()),
        "per_run_rates": {ts: round(float(v), 4) for ts, v in per_run.items()},
    }


def print_table(df: pd.DataFrame, title: str) -> None:
    print(f"\n{title}:")
    print(df.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--glob", default="redteam_eval_results_*.json",
                         help="Glob pattern for result files (default: %(default)s)")
    parser.add_argument("--dir", default=".", help="Directory to search (default: cwd)")
    parser.add_argument("--output", default="redteam_aggregate_results.json",
                         help="Where to write the aggregate JSON (default: %(default)s)")
    args = parser.parse_args()

    directory = Path(args.dir)
    runs = load_runs(args.glob, directory)
    df = flatten(runs)

    n_scorable = int(df["passed"].notna().sum())
    n_total = len(df)
    print(f"Loaded {len(runs)} run(s), {n_total} test cases ({n_scorable} scorable):")
    for run in runs:
        cfg = run["config"]
        print(f"  {run['_file']}: attacker={cfg['attacker_model']} "
              f"judge={cfg['judge_model']} n={len(run['results'])}")

    overall = overall_rate(df)
    print(f"\n{'='*70}\nOVERALL (across {overall['n_runs']} run(s))")
    print(f"  mean attack success rate: {overall['mean_rate']:.1%}  "
          f"(std across runs: {overall['std_rate']:.1%})")
    print(f"  pooled: {overall['pooled_successes']} / {overall['pooled_n']} attacks got through")
    for ts, rate in overall["per_run_rates"].items():
        print(f"    run {ts}: {rate:.1%}")

    by_vuln = per_run_rate(df, "vulnerability_id")
    by_category = per_run_rate(df, "category")
    by_technique = per_run_rate(df, "technique")

    print_table(by_vuln, "By vulnerability (mean/std of per-run rate across runs; pooled_n/successes for context)")
    print_table(by_category, "By category")
    print_table(by_technique, "By technique")

    output_path = directory / args.output
    payload = {
        "n_runs": len(runs),
        "run_files": [r["_file"] for r in runs],
        "run_configs": [
            {"file": r["_file"], "timestamp": r["timestamp"], **r["config"]}
            for r in runs
        ],
        "overall": overall,
        "by_vulnerability": by_vuln.to_dict(orient="records"),
        "by_category": by_category.to_dict(orient="records"),
        "by_technique": by_technique.to_dict(orient="records"),
    }
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nAggregate written to {output_path}")


if __name__ == "__main__":
    main()
