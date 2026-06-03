#!/usr/bin/env python3
"""Evaluate KB source routing for the NF Portal multi-source Bedrock Agent.

Invokes the agent with each turn in each session (reusing session IDs across
turns), captures Bedrock trace events to detect which KB source was used
(DOCS knowledge base vs. GRAPH action groups), and reports KB source selection
accuracy alongside answer quality metrics.

Usage:
    python evaluate_kb_routing.py
    python evaluate_kb_routing.py --agent-id WU3QRWA0FQ --alias-id TSTALIASID
    python evaluate_kb_routing.py --dataset kb_routing_dataset.json --profile my-profile

Detection logic:
    DOCS:  KNOWLEDGE_BASE invocation in trace (or WEB-type citation in response chunk)
    GRAPH: ACTION_GROUP invocation in trace (SPARQL Lambda calls)
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pandas as pd


# ---------------------------------------------------------------------------
# Agent invocation with trace
# ---------------------------------------------------------------------------

def invoke_agent(
    agent_client,
    agent_id: str,
    agent_alias_id: str,
    question: str,
    session_id: str,
) -> tuple[str, list[str], set[str]]:
    """Invoke agent and return (response_text, cited_urls, kb_sources_used).

    kb_sources_used is a set of "DOCS" and/or "GRAPH" detected from trace events
    and response chunk citations.
    """
    response = agent_client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=question,
        enableTrace=True,
    )

    completion = ""
    cited_urls: list[str] = []
    kb_sources_used: set[str] = set()

    for event in response["completion"]:
        # Response text and WEB citations
        if "chunk" in event:
            chunk = event["chunk"]
            completion += chunk["bytes"].decode("utf-8")
            for citation in chunk.get("attribution", {}).get("citations", []):
                for ref in citation.get("retrievedReferences", []):
                    location = ref.get("location", {})
                    if location.get("type") == "WEB":
                        url = location.get("webLocation", {}).get("url")
                        if url and url not in cited_urls:
                            cited_urls.append(url)
                        kb_sources_used.add("DOCS")

        # Trace events for orchestration steps
        if "trace" in event:
            trace_data = event["trace"].get("trace", {})
            orch = trace_data.get("orchestrationTrace", {})

            # Detect via invocationInput (pre-call)
            inv_input = orch.get("invocationInput", {})
            inv_type = inv_input.get("invocationType", "")
            if inv_type == "ACTION_GROUP":
                kb_sources_used.add("GRAPH")
            elif inv_type == "KNOWLEDGE_BASE":
                kb_sources_used.add("DOCS")

            # Detect via observation (post-call confirmation)
            obs = orch.get("observation", {})
            obs_type = obs.get("type", "")
            if obs_type == "ACTION_GROUP":
                kb_sources_used.add("GRAPH")
            elif obs_type == "KNOWLEDGE_BASE":
                kb_sources_used.add("DOCS")

    return completion.strip(), cited_urls, kb_sources_used


# ---------------------------------------------------------------------------
# KB source selection scoring
# ---------------------------------------------------------------------------

def score_kb_selection(expected_kb: str, kb_sources_used: set[str]) -> dict:
    """Score whether the agent used the expected KB source(s).

    Scoring:
      2 — correct: all expected sources used (extras acceptable); or NONE and no sources used
      1 — partial: expected BOTH but only one source used
      0 — wrong: used a source when NONE expected, or used wrong/no source when one was expected
     -1 — no trace detected (excluded from accuracy reporting)

    Returns dict with kb_used, kb_score, kb_correct.
    """
    if expected_kb == "DOCS":
        expected = {"DOCS"}
    elif expected_kb == "GRAPH":
        expected = {"GRAPH"}
    elif expected_kb == "BOTH":
        expected = {"DOCS", "GRAPH"}
    elif expected_kb == "NONE":
        expected = set()
        if not kb_sources_used:
            return {"kb_used": [], "kb_score": 2, "kb_correct": True}
        else:
            return {"kb_used": sorted(kb_sources_used), "kb_score": 0, "kb_correct": False}
    else:
        expected = set()

    if not kb_sources_used:
        return {"kb_used": [], "kb_score": -1, "kb_correct": False}

    correct_used = expected & kb_sources_used

    if expected.issubset(kb_sources_used):
        # All expected sources present (may have used extras)
        kb_score = 2
        kb_correct = True
    elif correct_used:
        # Partial: some expected sources used
        kb_score = 1
        kb_correct = False
    else:
        # None of the expected sources used
        kb_score = 0
        kb_correct = False

    return {
        "kb_used": sorted(kb_sources_used),
        "kb_score": kb_score,
        "kb_correct": kb_correct,
    }


# ---------------------------------------------------------------------------
# LLM judge for answer quality
# ---------------------------------------------------------------------------

def judge_answer(
    bedrock_client,
    judge_model_id: str,
    question: str,
    agent_response: str,
    expected_kb: str,
) -> int:
    """Score answer quality without a gold answer.

    Judges whether the response is a coherent, helpful answer to the question
    given what type of source should have been used.

    Returns:
      2 — clear, on-topic, informative answer
      1 — partial or vague answer
      0 — off-topic, evasive, or error response
     -1 — judge failure
    """
    source_hint = {
        "DOCS": "documentation/process/policy information",
        "GRAPH": "specific data counts, lists, or records from the NF portal knowledge graph",
        "BOTH": "a combination of documentation guidance and specific portal data",
    }.get(expected_kb, "relevant information")

    prompt = (
        "You are evaluating an AI assistant's response for the NF Data Portal.\n\n"
        f"User question: {question}\n\n"
        f"Expected answer type: {source_hint}\n\n"
        f"Assistant's response: {agent_response}\n\n"
        "Score whether the response is a coherent, helpful answer to the question:\n"
        "  2 — clear and informative; directly addresses what was asked\n"
        "  1 — partially answers the question; vague or incomplete\n"
        "  0 — off-topic, evasive, states it cannot answer, or is an error\n\n"
        "Reply with a single digit (0, 1, or 2) and nothing else."
    )

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8,
        "messages": [{"role": "user", "content": prompt}],
    })
    resp = bedrock_client.invoke_model(modelId=judge_model_id, body=body)
    digit = json.loads(resp["body"].read())["content"][0]["text"].strip()
    return int(digit) if digit in ("0", "1", "2") else -1


# ---------------------------------------------------------------------------
# Per-turn evaluation
# ---------------------------------------------------------------------------

def evaluate_turn(
    agent_client,
    bedrock_client,
    agent_id: str,
    agent_alias_id: str,
    judge_model_id: str,
    session_id: str,
    turn: dict,
    turn_number: int,
) -> dict:
    """Evaluate a single turn within a session."""
    question = turn["question"]
    expected_kb = turn["expected_kb"]
    persona = turn["persona"]

    agent_response, cited_urls, kb_sources_used = invoke_agent(
        agent_client, agent_id, agent_alias_id, question, session_id
    )

    kb_result = score_kb_selection(expected_kb, kb_sources_used)
    answer_score = judge_answer(bedrock_client, judge_model_id, question, agent_response, expected_kb)

    return {
        "session_id": session_id,
        "turn_id": turn["id"],
        "turn_number": turn_number,
        "question": question,
        "persona": persona,
        "expected_kb": expected_kb,
        "kb_used": kb_result["kb_used"],
        "kb_score": kb_result["kb_score"],
        "kb_correct": kb_result["kb_correct"],
        "cited_urls": cited_urls,
        "answer_score": answer_score,
        "answer_correct": answer_score == 2,
        "agent_response": agent_response,
    }


# ---------------------------------------------------------------------------
# Metrics reporting
# ---------------------------------------------------------------------------

def print_metrics(results: list[dict]) -> None:
    """Print KB routing evaluation metrics to stdout."""
    df = pd.DataFrame(results)

    n = len(df)
    print(f"\n{'='*60}")
    print(f"KB ROUTING EVALUATION RESULTS  ({n} turns across {df['session_id'].nunique()} sessions)")
    print(f"{'='*60}")

    # --- KB source selection accuracy ---
    # Exclude turns where kb_score is None (no expected_kb set) or -1 (no trace)
    kb_df = df[df["kb_score"].notna() & (df["kb_score"] != -1)]
    if len(kb_df) > 0:
        kb_acc = kb_df["kb_correct"].mean()
        kb_full = (kb_df["kb_score"] == 2).mean()
        kb_partial = (kb_df["kb_score"] == 1).mean()
        kb_wrong = (kb_df["kb_score"] == 0).mean()
        no_trace = (df["kb_score"] == -1).sum()
        print(f"\nKB source selection accuracy: {kb_acc:.1%}  ({kb_df['kb_correct'].sum():.0f} / {len(kb_df)})")
        print(f"  Full credit (score=2): {kb_full:.1%}")
        print(f"  Partial    (score=1): {kb_partial:.1%}")
        print(f"  Wrong      (score=0): {kb_wrong:.1%}")
        if no_trace > 0:
            print(f"  No trace detected:    {no_trace} turns (excluded from accuracy)")
    else:
        print("\nKB source selection: no scorable turns")

    # --- Per expected_kb accuracy ---
    print("\nKB selection accuracy by expected source:")
    for kb_type in ["DOCS", "GRAPH", "BOTH"]:
        sub = kb_df[kb_df["expected_kb"] == kb_type]
        if len(sub) > 0:
            acc = sub["kb_correct"].mean()
            print(f"  {kb_type:<6} {acc:.1%}  ({sub['kb_correct'].sum():.0f} / {len(sub)})")

    # --- What source was actually used vs expected ---
    print("\nActual KB usage distribution:")
    used_counts = pd.Series([str(sorted(r["kb_used"])) for r in results]).value_counts()
    for label, count in used_counts.items():
        print(f"  {label}: {count}")

    # --- Answer quality ---
    ans_df = df[df["answer_score"] != -1]
    if len(ans_df) > 0:
        ans_acc = (ans_df["answer_score"] == 2).mean()
        print(f"\nAnswer quality (judge score=2): {ans_acc:.1%}  ({(ans_df['answer_score']==2).sum()} / {len(ans_df)})")
        score_map = {-1: "judge failed", 0: "off-topic/error", 1: "partial", 2: "correct"}
        score_dist = df["answer_score"].value_counts().sort_index()
        score_dist.index = score_dist.index.map(score_map)
        print(f"  Distribution:\n{score_dist.to_string()}")

    # --- Per-persona KB accuracy ---
    if len(kb_df) > 0:
        print("\nKB selection accuracy by persona:")
        persona_acc = (
            kb_df.groupby("persona")["kb_correct"]
            .agg(accuracy="mean", n="count")
            .sort_values("accuracy", ascending=False)
            .reset_index()
        )
        persona_acc["accuracy"] = persona_acc["accuracy"].map("{:.1%}".format)
        print(persona_acc.to_string(index=False))

    # --- Single-turn vs multi-turn accuracy ---
    if len(kb_df) > 0:
        single = kb_df[kb_df["turn_number"] == 1]["kb_correct"].mean()
        multi = kb_df[kb_df["turn_number"] > 1]["kb_correct"].mean()
        n_single = (kb_df["turn_number"] == 1).sum()
        n_multi = (kb_df["turn_number"] > 1).sum()
        print(f"\nKB accuracy — turn 1 (no prior context): {single:.1%}  (n={n_single})")
        print(f"KB accuracy — turn 2+ (with prior context): {multi:.1%}  (n={n_multi})")

    print(f"\n{'='*60}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_evaluation(args: argparse.Namespace) -> None:
    """Run the full KB routing evaluation pipeline."""
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    agent_client = session.client("bedrock-agent-runtime")
    bedrock_client = session.client("bedrock-runtime")

    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Authenticated as: {identity['Arn']}")
    print(f"Region: {args.region}")

    dataset_path = Path(args.dataset)
    with open(dataset_path) as f:
        dataset = json.load(f)

    total_turns = sum(len(s["turns"]) for s in dataset)
    print(f"Loaded {len(dataset)} sessions ({total_turns} turns) from {dataset_path.name}")

    results: list[dict] = []
    errors: list[dict] = []

    for si, session_data in enumerate(dataset, 1):
        # Each session uses a fresh Bedrock session so prior turns are in context
        bedrock_session_id = str(uuid.uuid4())
        n_turns = len(session_data["turns"])
        print(f"\n[Session {si}/{len(dataset)}] {session_data['description']!r}  ({n_turns} turns)")

        for ti, turn in enumerate(session_data["turns"], 1):
            label = f"  Turn {ti}/{n_turns}: [{turn['expected_kb']}] {turn['question'][:65]}..."
            print(label, flush=True)
            try:
                result = evaluate_turn(
                    agent_client,
                    bedrock_client,
                    args.agent_id,
                    args.alias_id,
                    args.judge_model,
                    bedrock_session_id,
                    turn,
                    ti,
                )
                results.append(result)
                kb_status = "OK" if result["kb_correct"] else f"WRONG (used {result['kb_used']})"
                print(f"    KB: {kb_status}  |  Answer score: {result['answer_score']}")
            except Exception as e:
                errors.append({
                    "session_id": session_data["session_id"],
                    "turn_id": turn["id"],
                    "error": str(e),
                })
                print(f"    ERROR: {e}")

    print(f"\nCompleted: {len(results)} turns scored, {len(errors)} errors")

    # Save results
    output_path = Path(args.output)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dated_path = output_path.with_name(f"{output_path.stem}_{timestamp}{output_path.suffix}")

    payload = {
        "timestamp": timestamp,
        "config": {
            "agent_id": args.agent_id,
            "agent_alias_id": args.alias_id,
            "judge_model": args.judge_model,
            "dataset": str(dataset_path),
        },
        "results": results,
        "errors": errors,
    }

    dated_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dated_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"Results saved to {dated_path}")

    if results:
        print_metrics(results)
    else:
        print("No results to report.")

    if errors:
        sys.exit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate KB source routing for the NF Portal multi-source Bedrock Agent.",
    )
    parser.add_argument(
        "--agent-id",
        default="WU3QRWA0FQ",
        help="Bedrock Agent ID (default: %(default)s)",
    )
    parser.add_argument(
        "--alias-id",
        default="TSTALIASID",
        help="Bedrock Agent alias ID (default: %(default)s)",
    )
    parser.add_argument(
        "--profile",
        default="default",
        help="AWS profile name (default: %(default)s)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: %(default)s)",
    )
    parser.add_argument(
        "--dataset",
        default="kb_routing_dataset.json",
        help="Path to the routing sessions dataset JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default="routing_eval_results.json",
        help="Base output path; a UTC datestamp is appended (default: %(default)s)",
    )
    parser.add_argument(
        "--judge-model",
        default="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        help="Bedrock model ID for the LLM judge (default: %(default)s)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    run_evaluation(parse_args())
