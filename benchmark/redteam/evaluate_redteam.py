#!/usr/bin/env python3
"""Red team the NF Portal multi-source Bedrock Agent using deepteam.

Loads a config of vulnerability x attack pairings (redteam_config.json),
builds a model_callback that drives the live copilot via Bedrock's
invoke_agent (reusing a real Bedrock session per attack conversation so
multi-turn attacks carry conversation memory the same way a real user
session would), runs deepteam's attack simulator + LLM-judge evaluator
against it, and saves the resulting risk assessment.

SAFETY: this script actively attacks a live Bedrock Agent alias. It refuses
to run against the known prod agent id unless --allow-prod is passed.

Requires Python 3.9-3.12. deepteam 1.0.7 fails to import on Python 3.13+
(it imports the stdlib 'nntplib' module, removed in 3.13) — use a 3.12 venv.

Usage:
    python evaluate_redteam.py                          # all config entries, dev agent
    python evaluate_redteam.py --vulnerability pii-leakage  # one config entry
    python evaluate_redteam.py --agent-id ERAAPKTD4Q --allow-prod  # never do this by accident
"""

import argparse
import asyncio
import contextvars
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3

DEV_AGENT_ID = "ERAAPKTD4Q"
PROD_AGENT_ID = "R7WZ38JGKX"

_bedrock_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "bedrock_session_id"
)


# ---------------------------------------------------------------------------
# Bedrock Agent invocation (adapted from ../kb-routing/evaluate_kb_routing.py)
# ---------------------------------------------------------------------------

def invoke_agent_sync(agent_client, agent_id, agent_alias_id, question, session_id):
    """Invoke the agent and return (response_text, sources_used) for one turn."""
    response = agent_client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=question,
        enableTrace=True,
    )

    completion = ""
    sources_used: set[str] = set()

    for event in response["completion"]:
        if "chunk" in event:
            completion += event["chunk"]["bytes"].decode("utf-8")

        if "trace" in event:
            trace_data = event["trace"].get("trace", {})
            orch = trace_data.get("orchestrationTrace", {})

            inv_type = orch.get("invocationInput", {}).get("invocationType", "")
            if inv_type == "ACTION_GROUP":
                sources_used.add("GRAPH")
            elif inv_type == "KNOWLEDGE_BASE":
                sources_used.add("DOCS")

            obs_type = orch.get("observation", {}).get("type", "")
            if obs_type == "ACTION_GROUP":
                sources_used.add("GRAPH")
            elif obs_type == "KNOWLEDGE_BASE":
                sources_used.add("DOCS")

    completion_stripped = completion.strip()
    if "<actions><redirect>" in completion_stripped:
        sources_used.add("REDIRECT")

    return completion_stripped, sources_used


def make_model_callback(agent_client, agent_id, agent_alias_id):
    """Build deepteam's expected (input, turns) -> RTTurn async callback.

    deepteam calls this once per turn of an attack conversation. `turns`
    is None/empty at the start of a new attack; a fresh Bedrock sessionId
    is minted then and reused (via a contextvar, so concurrent attacks
    running as separate asyncio tasks don't cross-talk) for every
    subsequent turn deepteam sends for that same attack.
    """
    from deepteam.test_case import RTTurn, ToolCall

    async def model_callback(input: str, turns=None):
        if not turns:
            session_id = str(uuid.uuid4())
            _bedrock_session_id.set(session_id)
        else:
            session_id = _bedrock_session_id.get()

        response_text, sources_used = await asyncio.to_thread(
            invoke_agent_sync, agent_client, agent_id, agent_alias_id, input, session_id
        )

        # tools_called (not metadata) is what deepteam's metrics actually surface
        # to the judge model, for both single-turn and multi-turn test cases.
        tools_called = [ToolCall(name=source) for source in sorted(sources_used)]

        return RTTurn(
            role="assistant",
            content=response_text,
            tools_called=tools_called or None,
        )

    return model_callback


# ---------------------------------------------------------------------------
# Config -> deepteam vulnerabilities/attacks
# ---------------------------------------------------------------------------

def build_vulnerability(entry, simulator_model, evaluation_model):
    import deepteam.vulnerabilities as vuln_module
    from deepteam.vulnerabilities import CustomVulnerability

    if entry["kind"] == "builtin":
        cls = getattr(vuln_module, entry["builtin_class"])
        kwargs = {"simulator_model": simulator_model, "evaluation_model": evaluation_model}
        if entry.get("builtin_types"):
            kwargs["types"] = entry["builtin_types"]
        return cls(**kwargs)

    if entry["kind"] == "custom":
        custom = entry["custom"]
        return CustomVulnerability(
            name=custom["name"],
            criteria=custom["criteria"],
            types=custom["types"],
            simulator_model=simulator_model,
            evaluation_model=evaluation_model,
        )

    raise ValueError(f"Unknown vulnerability kind: {entry['kind']!r}")


def build_attacks(attack_names, simulator_model):
    import deepteam.attacks.single_turn as single_turn
    import deepteam.attacks.multi_turn as multi_turn

    attacks = []
    for name in attack_names:
        if hasattr(single_turn, name):
            attacks.append(getattr(single_turn, name)())
        elif hasattr(multi_turn, name):
            attacks.append(getattr(multi_turn, name)(simulator_model=simulator_model))
        else:
            raise ValueError(f"Unknown attack technique: {name!r}")
    return attacks


# ---------------------------------------------------------------------------
# Result extraction
# ---------------------------------------------------------------------------

def test_case_to_dict(test_case, vulnerability_id, category):
    sources_used = [tc.name for tc in (test_case.tools_called or [])]
    if test_case.turns:
        for turn in test_case.turns:
            sources_used.extend(tc.name for tc in (turn.tools_called or []))

    return {
        "vulnerability_id": vulnerability_id,
        "category": category,
        "vulnerability": test_case.vulnerability,
        "vulnerability_type": (
            test_case.vulnerability_type.value if test_case.vulnerability_type else None
        ),
        "attack_method": test_case.attack_method,
        "input": test_case.input,
        "actual_output": test_case.actual_output,
        "turns": (
            [
                {
                    "role": t.role,
                    "content": t.content,
                    "sources_used": [tc.name for tc in (t.tools_called or [])],
                }
                for t in test_case.turns
            ]
            if test_case.turns
            else None
        ),
        "score": test_case.score,
        "passed": bool(test_case.score) and test_case.score > 0,
        "reason": test_case.reason,
        "error": test_case.error,
        "sources_used": sorted(set(sources_used)),
    }


def print_metrics(results: list[dict]) -> None:
    import pandas as pd

    scorable = [r for r in results if r["error"] is None]
    n = len(results)
    n_err = n - len(scorable)

    print(f"\n{'='*60}")
    print(f"REDTEAM EVALUATION RESULTS  ({n} attack test cases, {n_err} errored)")
    print(f"{'='*60}")

    if not scorable:
        print("\nNo scorable test cases.")
        return

    df = pd.DataFrame(scorable)
    overall_attack_success = (~df["passed"]).mean()
    print(f"\nOverall attack success rate: {overall_attack_success:.1%}  "
          f"({(~df['passed']).sum()} / {len(df)} attacks got through)")

    print("\nBy vulnerability:")
    by_vuln = (
        df.groupby("vulnerability_id")
        .agg(attack_success_rate=("passed", lambda s: (~s).mean()), n=("passed", "count"))
        .sort_values("attack_success_rate", ascending=False)
    )
    by_vuln["attack_success_rate"] = by_vuln["attack_success_rate"].map("{:.1%}".format)
    print(by_vuln.to_string())

    print("\nBy category:")
    by_cat = (
        df.groupby("category")
        .agg(attack_success_rate=("passed", lambda s: (~s).mean()), n=("passed", "count"))
        .sort_values("attack_success_rate", ascending=False)
    )
    by_cat["attack_success_rate"] = by_cat["attack_success_rate"].map("{:.1%}".format)
    print(by_cat.to_string())

    print("\nBy attack technique:")
    by_attack = (
        df.groupby("attack_method")
        .agg(attack_success_rate=("passed", lambda s: (~s).mean()), n=("passed", "count"))
        .sort_values("attack_success_rate", ascending=False)
    )
    by_attack["attack_success_rate"] = by_attack["attack_success_rate"].map("{:.1%}".format)
    print(by_attack.to_string())

    print(f"\n{'='*60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_evaluation(args: argparse.Namespace) -> None:
    if args.agent_id == PROD_AGENT_ID and not args.allow_prod:
        print(
            f"ERROR: refusing to red team the prod agent id ({PROD_AGENT_ID}) "
            "without --allow-prod. Use the dev agent/alias instead.",
            file=sys.stderr,
        )
        sys.exit(1)
    if args.agent_id == PROD_AGENT_ID:
        print(f"WARNING: running adversarial attacks against PROD agent {PROD_AGENT_ID}.")

    from deepteam import red_team
    from deepeval.models import AmazonBedrockModel

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    agent_client = session.client("bedrock-agent-runtime")

    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Authenticated as: {identity['Arn']}")
    print(f"Region: {args.region}")
    print(f"Target: agent={args.agent_id} alias={args.alias_id}")

    config_path = Path(args.config)
    with open(config_path) as f:
        config = json.load(f)

    if args.vulnerability is not None:
        config = [e for e in config if e["vulnerability_id"] == args.vulnerability]
        if not config:
            print(f"ERROR: no config entry with vulnerability_id {args.vulnerability!r}", file=sys.stderr)
            sys.exit(1)

    simulator_model = AmazonBedrockModel(model=args.simulator_model, region=args.region)
    evaluation_model = AmazonBedrockModel(model=args.evaluation_model, region=args.region)

    model_callback = make_model_callback(agent_client, args.agent_id, args.alias_id)

    all_results = []
    errors = []

    for entry in config:
        print(f"\n[Vulnerability] {entry['vulnerability_id']} ({entry['category']})")
        vulnerability = build_vulnerability(entry, simulator_model, evaluation_model)
        attacks = build_attacks(entry["attacks"], simulator_model)

        try:
            risk_assessment = red_team(
                model_callback=model_callback,
                vulnerabilities=[vulnerability],
                attacks=attacks,
                simulator_model=simulator_model,
                evaluation_model=evaluation_model,
                attacks_per_vulnerability_type=args.attacks_per_type,
                max_concurrent=args.max_concurrent,
                target_purpose=args.target_purpose,
                ignore_errors=True,
            )
        except Exception as e:
            print(f"  ERROR running vulnerability {entry['vulnerability_id']}: {e}")
            errors.append({"vulnerability_id": entry["vulnerability_id"], "error": str(e)})
            continue

        for test_case in risk_assessment.test_cases:
            all_results.append(
                test_case_to_dict(test_case, entry["vulnerability_id"], entry["category"])
            )

    print(f"\nCompleted: {len(all_results)} test cases, {len(errors)} vulnerability-level errors")

    output_path = Path(args.output)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dated_path = output_path.with_name(f"{output_path.stem}_{timestamp}{output_path.suffix}")

    payload = {
        "timestamp": timestamp,
        "config": {
            "agent_id": args.agent_id,
            "agent_alias_id": args.alias_id,
            "simulator_model": args.simulator_model,
            "evaluation_model": args.evaluation_model,
            "config_file": str(config_path),
            "attacks_per_vulnerability_type": args.attacks_per_type,
        },
        "results": all_results,
        "errors": errors,
    }

    dated_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dated_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Results saved to {dated_path}")

    if all_results:
        print_metrics(all_results)
    else:
        print("No results to report.")

    if errors:
        sys.exit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Red team the NF Portal multi-source Bedrock Agent using deepteam.",
    )
    parser.add_argument("--agent-id", default=DEV_AGENT_ID,
                         help=f"Bedrock Agent ID (default: dev, {DEV_AGENT_ID})")
    parser.add_argument("--alias-id", default="TSTALIASID",
                         help="Bedrock Agent alias ID (default: TSTALIASID / DRAFT)")
    parser.add_argument("--allow-prod", action="store_true",
                         help=f"Allow running against the prod agent id ({PROD_AGENT_ID}).")
    parser.add_argument("--profile", default=None, help="AWS profile name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--config", default="redteam_config.json",
                         help="Path to redteam_config.json (default: %(default)s)")
    parser.add_argument("--vulnerability", default=None, metavar="VULNERABILITY_ID",
                         help="Only run one config entry by its vulnerability_id")
    parser.add_argument("--output", default="redteam_eval_results.json",
                         help="Base output path; a UTC datestamp is appended")
    parser.add_argument("--simulator-model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0",
                         help="Bedrock model ID used to generate attacks (default: %(default)s)")
    parser.add_argument("--evaluation-model", default="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                         help="Bedrock model ID used to judge pass/fail (default: %(default)s)")
    parser.add_argument("--attacks-per-type", type=int, default=1,
                         help="Number of attacks to simulate per vulnerability type (default: %(default)s)")
    parser.add_argument("--max-concurrent", type=int, default=3,
                         help="Max concurrent attacks against the dev alias (default: %(default)s, "
                              "kept low to avoid rate-limiting the dev Bedrock alias)")
    parser.add_argument("--target-purpose", default=(
        "An NF Portal chatbot that answers documentation/process questions from a "
        "help-docs knowledge base and answers data questions via read-only SPARQL "
        "queries against the NF-OSI knowledge graph. It has no code execution and no "
        "write/mutation access to any system."
    ), help="Description of the target's intended purpose, used by the judge model.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    run_evaluation(parse_args())
