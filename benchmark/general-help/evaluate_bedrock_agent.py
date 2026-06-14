#!/usr/bin/env python3
"""Evaluate AWS Bedrock Agent — NF Portal General Help

Invokes the deployed NF portal chatbot (Bedrock Agent) with each question from
the help_qa_dataset benchmark, scores responses with an LLM judge, and reports
accuracy metrics.

Usage:
    python evaluate_bedrock_agent.py
    python evaluate_bedrock_agent.py --agent-id ABC123 --alias-id XYZ789
    python evaluate_bedrock_agent.py --dataset help_qa_dataset_openai.json --profile my-aws-profile
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
# Agent invocation
# ---------------------------------------------------------------------------

def invoke_agent(
    agent_client,
    agent_id: str,
    agent_alias_id: str,
    question: str,
    session_id: str | None = None,
) -> tuple[str, list[str]]:
    """Send a question to the Bedrock agent.

    Returns (response_text, cited_urls) where cited_urls are the web URLs
    retrieved from the Knowledge Base (web crawler source).
    """
    if session_id is None:
        session_id = str(uuid.uuid4())

    response = agent_client.invoke_agent(
        agentId=agent_id,
        agentAliasId=agent_alias_id,
        sessionId=session_id,
        inputText=question,
    )

    completion = ""
    cited_urls: list[str] = []

    for event in response["completion"]:
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

    return completion.strip(), cited_urls


# ---------------------------------------------------------------------------
# LLM judge
# ---------------------------------------------------------------------------

def judge_response(
    bedrock_client,
    judge_model_id: str,
    question: str,
    correct_answer: str,
    agent_response: str,
) -> int:
    """Score how well the agent's response matches the correct answer.

    Returns:
      0 — incorrect or contradicts the correct answer
      1 — partially correct or vague
      2 — correct, clearly corresponds to the correct answer
     -1 — judge failed to return a valid score
    """
    prompt = (
        "You are evaluating an AI assistant's response to a question.\n\n"
        f"Question: {question}\n\n"
        f"Correct answer: {correct_answer}\n\n"
        f"Assistant's response: {agent_response}\n\n"
        "Score how well the assistant's response corresponds to the correct answer:\n"
        "  0 — incorrect or contradicts the correct answer\n"
        "  1 — partially correct or vague\n"
        "  2 — correct, clearly corresponds to the correct answer\n\n"
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
# Scoring
# ---------------------------------------------------------------------------

def score_question(
    bedrock_client,
    judge_model_id: str,
    q: dict,
    agent_response: str,
    cited_urls: list[str],
) -> dict:
    """Score one question and return a result dict."""
    choices = q["mc1_targets"]["choices"]
    labels = q["mc1_targets"]["labels"]
    correct_answer = choices[labels.index(1)]

    judge_score = judge_response(
        bedrock_client, judge_model_id, q["question"], correct_answer, agent_response
    )

    expected_urls = set(q.get("page_urls", []))
    attribution_hit = bool(expected_urls & set(cited_urls)) if expected_urls else None

    return {
        "question": q["question"],
        "persona": q["persona"],
        "cross_page": len(q.get("page_urls", [])) > 1,
        "expected_urls": list(expected_urls),
        "cited_urls": cited_urls,
        "attribution_hit": attribution_hit,
        "correct_answer": correct_answer,
        "judge_score": judge_score,
        "correct": judge_score == 2,
        "agent_response": agent_response,
    }


# ---------------------------------------------------------------------------
# Metrics reporting
# ---------------------------------------------------------------------------

def print_metrics(results: list[dict]) -> None:
    """Print evaluation metrics to stdout."""
    df = pd.DataFrame(results)

    # Overall accuracy
    overall = df["correct"].mean()
    print(f"\nOverall accuracy: {overall:.1%}  ({df['correct'].sum()} / {len(df)})")

    # Score distribution
    score_map = {-1: "judge failed", 0: "incorrect", 1: "partial", 2: "correct"}
    score_dist = df["judge_score"].value_counts().sort_index()
    score_dist.index = score_dist.index.map(score_map)
    print(f"\nScore distribution:\n{score_dist.to_string()}")

    # Per-persona accuracy
    persona_acc = (
        df.groupby("persona")["correct"]
        .agg(accuracy="mean", n="count", correct="sum")
        .sort_values("accuracy", ascending=False)
        .reset_index()
    )
    persona_acc["accuracy"] = persona_acc["accuracy"].map("{:.1%}".format)
    print(f"\nPer-persona accuracy:\n{persona_acc.to_string(index=False)}")

    # Cross-page vs single-page
    cross_acc = (
        df.groupby("cross_page")["correct"]
        .agg(accuracy="mean", n="count")
        .rename(index={True: "cross-page", False: "single-page"})
        .reset_index()
        .rename(columns={"cross_page": "type"})
    )
    cross_acc["accuracy"] = cross_acc["accuracy"].map("{:.1%}".format)
    print(f"\nCross-page vs single-page accuracy:\n{cross_acc.to_string(index=False)}")

    # Source attribution
    attributed = df[df["attribution_hit"].notna()]
    if len(attributed) > 0:
        attr_rate = attributed["attribution_hit"].mean()
        print(
            f"\nSource attribution rate: {attr_rate:.1%}  "
            f"({attributed['attribution_hit'].sum():.0f} / {len(attributed)} "
            f"questions with expected URLs)"
        )
    else:
        print("\nSource attribution: no questions had expected URLs")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_evaluation(args: argparse.Namespace) -> None:
    """Run the full evaluation pipeline."""
    # AWS clients
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    agent_client = session.client("bedrock-agent-runtime")
    bedrock_client = session.client("bedrock-runtime")

    # Verify credentials
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    print(f"Authenticated as: {identity['Arn']}")
    print(f"Region: {args.region}")

    # Load dataset
    dataset_path = Path(args.dataset)
    with open(dataset_path) as f:
        dataset = json.load(f)
    print(f"Loaded {len(dataset)} questions from {dataset_path.name}")

    # Evaluate
    results: list[dict] = []
    errors: list[dict] = []

    for i, q in enumerate(dataset, 1):
        print(f"  [{i}/{len(dataset)}] {q['question'][:70]}...", flush=True)
        try:
            agent_response, cited_urls = invoke_agent(
                agent_client, args.agent_id, args.alias_id, q["question"]
            )
            result = score_question(
                bedrock_client, args.judge_model, q, agent_response, cited_urls
            )
            results.append(result)
        except Exception as e:
            errors.append({"question": q["question"], "error": str(e)})
            print(f"    ERROR: {e}")

    print(f"\nCompleted: {len(results)} scored, {len(errors)} errors")

    # Save results with datestamp
    output_path = Path(args.output)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = output_path.stem
    suffix = output_path.suffix
    dated_path = output_path.with_name(f"{stem}_{timestamp}{suffix}")

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

    # Metrics
    if results:
        print_metrics(results)
    else:
        print("No results to report.")

    if errors:
        sys.exit(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the NF Portal Bedrock Agent against help_qa_dataset.",
    )
    parser.add_argument(
        "--agent-id",
        default="ERAAPKTD4Q",
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
        default="help_qa_dataset_anthropic.json",
        help="Path to benchmark dataset JSON (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default="eval_results.json",
        help="Output path for results; a datestamp is appended to the filename (default: %(default)s)",
    )
    parser.add_argument(
        "--judge-model",
        default="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        help="Bedrock model ID for the LLM judge (default: %(default)s)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    run_evaluation(parse_args())
