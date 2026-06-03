#!/usr/bin/env python3
"""Update the 'Seed dataset composition' table in README.md from kb_routing_dataset.json.

Run after any changes to the dataset:
    python update_readme_stats.py
"""

import json
import re
from pathlib import Path

DATASET = Path("kb_routing_dataset.json")
README = Path("README.md")

SESSION_TYPES = ["DOCS", "GRAPH", "MIXED", "BOTH", "NONE"]

TABLE_RE = re.compile(
    r"(### Dataset composition\n\n)"   # heading preserved
    r"\|.*?\n"                               # header row
    r"\|[-| ]+\n"                            # separator row
    r"(?:\|.*?\n)+"                          # data rows (one or more)
    r"(\|.*?\n)",                            # total row (last row)
    re.DOTALL,
)


def compute_stats(data: list[dict]) -> dict:
    stats = {t: {"sessions": 0, "single": 0, "multi": 0, "turns": 0} for t in SESSION_TYPES}
    for session in data:
        t = session["session_type"]
        n = session["n_turns"]
        stats[t]["sessions"] += 1
        stats[t]["turns"] += n
        if n == 1:
            stats[t]["single"] += 1
        else:
            stats[t]["multi"] += 1
    return stats


def build_table(stats: dict) -> str:
    total_sessions = sum(v["sessions"] for v in stats.values())
    total_single = sum(v["single"] for v in stats.values())
    total_multi = sum(v["multi"] for v in stats.values())
    total_turns = sum(v["turns"] for v in stats.values())

    lines = [
        "| `session_type` | Sessions | Single-turn | Multi-turn | Turns |",
        "|----------------|----------|-------------|------------|-------|",
    ]
    for t in SESSION_TYPES:
        v = stats[t]
        single = str(v["single"]) if v["single"] else "—"
        multi = str(v["multi"]) if v["multi"] else "—"
        lines.append(f"| {t} | {v['sessions']} | {single} | {multi} | {v['turns']} |")
    lines.append(
        f"| **Total** | **{total_sessions}** | **{total_single}** | **{total_multi}** | **{total_turns}** |"
    )
    return "\n".join(lines) + "\n"


def update_readme(stats: dict) -> None:
    readme = README.read_text()
    new_table = build_table(stats)

    # Replace everything between the heading and the next --- separator
    section_re = re.compile(
        r"(### Dataset composition\n\n)"
        r"(\|[^\n]*\n\|[-| ]+\n(?:\|[^\n]*\n)+)",
    )
    match = section_re.search(readme)
    if not match:
        raise RuntimeError("Could not find 'Seed dataset composition' table in README.md")

    updated = readme[: match.start(2)] + new_table + readme[match.end(2) :]
    README.write_text(updated)
    print(f"README.md updated.")


def main() -> None:
    data = json.loads(DATASET.read_text())
    stats = compute_stats(data)

    print(f"{'Type':<8} {'Sessions':>8} {'Single':>8} {'Multi':>8} {'Turns':>8}")
    print("-" * 44)
    for t in SESSION_TYPES:
        v = stats[t]
        print(f"{t:<8} {v['sessions']:>8} {v['single']:>8} {v['multi']:>8} {v['turns']:>8}")
    totals = (
        sum(v["sessions"] for v in stats.values()),
        sum(v["single"] for v in stats.values()),
        sum(v["multi"] for v in stats.values()),
        sum(v["turns"] for v in stats.values()),
    )
    print("-" * 44)
    print(f"{'Total':<8} {totals[0]:>8} {totals[1]:>8} {totals[2]:>8} {totals[3]:>8}")

    update_readme(stats)


if __name__ == "__main__":
    main()
