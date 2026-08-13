#!/usr/bin/env python3
"""Upload benchmark log/result files to Synapse for provenance.

Generic uploader for gitignored log or result files (e.g. redteam
transcripts, which can contain content an attack successfully extracted
from the agent, or other benchmark outputs) that still need a durable,
permissioned home so a report citing their numbers stays independently
reproducible. Point it at any directory/pattern and any Synapse
folder/project.

Requires a Synapse account with upload access to the target folder/project
and login credentials available to synapseclient (~/.synapseConfig or the
SYNAPSE_AUTH_TOKEN environment variable).

Usage:
    # redteam runs -> the permissioned redteam results project
    python upload_logs_to_synapse.py --dir benchmark/redteam \\
        --pattern 'redteam_eval_results_*.json' --pattern 'redteam_aggregate_results.json' \\
        --parent-id syn76878333

    # explicit files
    python upload_logs_to_synapse.py --file benchmark/kb-routing/routing_eval_results_20260620T001142Z.json \\
        --parent-id syn12345678

    python upload_logs_to_synapse.py --dir benchmark/redteam --pattern 'redteam_eval_results_*.json' \\
        --parent-id syn76878333 --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

import synapseclient
from synapseclient import File


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dir", default=".", help="Directory to search for files matching --pattern (default: cwd)"
    )
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="Glob pattern (relative to --dir) to match files; repeatable.",
    )
    parser.add_argument(
        "--file",
        action="append",
        default=None,
        help="Explicit file path to upload; repeatable. Combines with --pattern.",
    )
    parser.add_argument(
        "--parent-id",
        required=True,
        help="Synapse folder/project id to upload into, e.g. syn76878333",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the files that would be uploaded without uploading them",
    )
    return parser.parse_args()


def find_files(directory: Path, patterns: list[str] | None, explicit: list[str] | None) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns or []:
        files.extend(sorted(directory.glob(pattern)))
    for f in explicit or []:
        path = Path(f)
        if not path.exists():
            raise SystemExit(f"File not found: {path}")
        files.append(path)
    if not files:
        raise SystemExit("No files to upload — pass --pattern and/or --file")
    return files


def main() -> None:
    args = parse_args()
    files = find_files(Path(args.dir), args.pattern, args.file)

    print(f"{len(files)} file(s) to upload to {args.parent_id}:")
    for f in files:
        print(f"  {f}")
    if args.dry_run:
        print("\n--dry-run: nothing uploaded")
        return

    syn = synapseclient.login()
    print()
    for f in files:
        entity = syn.store(File(str(f), parent=args.parent_id))
        print(f"  {f.name} -> {entity.id} (version {entity.versionNumber})")


if __name__ == "__main__":
    main()
