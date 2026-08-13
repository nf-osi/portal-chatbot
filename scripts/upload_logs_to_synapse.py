#!/usr/bin/env python3
"""Upload redteam result files to Synapse for provenance.

Result files (`redteam_eval_results_*.json`, `redteam_aggregate_results.json`)
are gitignored — they can contain content an attack successfully extracted
from the agent, so they don't belong in this public repo. Without them
committed anywhere, a report citing their numbers isn't independently
reproducible. This script uploads them to a permissioned Synapse
location instead, so runs behind a report stay traceable:
https://www.synapse.org/Synapse:syn76878333

Requires a Synapse account with upload access to that folder/project and
login credentials available to synapseclient (~/.synapseConfig or the
SYNAPSE_AUTH_TOKEN environment variable).

Usage:
    python upload_redteam_results.py                       # all result files in this dir
    python upload_redteam_results.py --dir /path/to/results
    python upload_redteam_results.py --file redteam_eval_results_20260710T190023Z.json
    python upload_redteam_results.py --dry-run
"""

from __future__ import annotations

import argparse
from pathlib import Path

import synapseclient
from synapseclient import File

DEFAULT_PARENT_ID = "syn76878333"
DEFAULT_GLOBS = ("redteam_eval_results_*.json", "redteam_aggregate_results.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dir", default=".", help="Directory to search for result files (default: cwd)"
    )
    parser.add_argument(
        "--file",
        action="append",
        default=None,
        help="Explicit file path to upload; repeatable. Overrides directory globbing.",
    )
    parser.add_argument(
        "--parent-id",
        default=DEFAULT_PARENT_ID,
        help=f"Synapse folder/project to upload into (default: {DEFAULT_PARENT_ID})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List the files that would be uploaded without uploading them",
    )
    return parser.parse_args()


def find_files(directory: Path, explicit: list[str] | None) -> list[Path]:
    if explicit:
        files = [Path(f) for f in explicit]
        missing = [f for f in files if not f.exists()]
        if missing:
            raise SystemExit(f"File(s) not found: {', '.join(str(m) for m in missing)}")
        return files
    files = []
    for pattern in DEFAULT_GLOBS:
        files.extend(sorted(directory.glob(pattern)))
    if not files:
        raise SystemExit(f"No result files matched {DEFAULT_GLOBS} in {directory}")
    return files


def main() -> None:
    args = parse_args()
    files = find_files(Path(args.dir), args.file)

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
