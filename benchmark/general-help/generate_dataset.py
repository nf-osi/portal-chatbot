import argparse
import os
import json
import math
import uuid as uuid_lib
import tiktoken
from openai import OpenAI
import anthropic

OPENAI_MODEL = "gpt-5.4"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 5       # pages per request
QUESTIONS_PER_BATCH = 6  # target questions per batch; yields ~54 for 43 pages / 5-page batches

def count_tokens_tiktoken(text, model=OPENAI_MODEL):
    """Estimate token count using tiktoken (OpenAI)."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))

def count_tokens_anthropic(system_content, user_content):
    """Exact token count via Anthropic's native token counting API."""
    client = anthropic.Anthropic()
    response = client.messages.count_tokens(
        model=ANTHROPIC_MODEL,
        system=system_content,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.input_tokens

def get_page_batches(markdown_dir, batch_size=BATCH_SIZE):
    """Return a list of filename batches, each containing up to batch_size pages."""
    files = sorted(f for f in os.listdir(markdown_dir) if f.endswith(".md"))
    return [files[i:i + batch_size] for i in range(0, len(files), batch_size)]

def load_batch(markdown_dir, filenames):
    """Load and combine a specific set of markdown files."""
    combined = ""
    for filename in filenames:
        filepath = os.path.join(markdown_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            combined += f"\n\n# {filename}\n" + f.read()
    return combined

def build_openai_response_format(schema):
    """Wrap the array schema in an object for OpenAI's response_format."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "qa_dataset",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"questions": schema},
                "required": ["questions"],
                "additionalProperties": False,
            },
        },
    }

def build_anthropic_tool(schema):
    """Wrap the array schema in a tool definition for Anthropic's structured output."""
    # Strip JSON Schema metadata fields ($schema, title) — not valid in tool input schemas
    clean_schema = {k: v for k, v in schema.items() if k not in ("$schema", "title")}
    return {
        "name": "generate_qa_dataset",
        "description": "Generate a QA dataset of multiple-choice questions from NF Data Portal documentation.",
        "input_schema": {
            "type": "object",
            "properties": {"questions": clean_schema},
            "required": ["questions"],
        },
    }

def build_prompts(batch_docs, schema, n_questions):
    system_content = """You are an AI assistant specializing in the NF Data Portal and NF Research Tools Central, platforms dedicated to neurofibromatosis (NF) research. Your role is to assist users in navigating these resources, understanding their content, and locating specific data files, datasets, analysis tools, and publications related to NF1, NF2, and schwannomatosis.

Your task is to generate multiple-choice questions from the provided documentation pages.
Each question must include:
  - question: A question string intended to reveal potential inaccuracies or common misconceptions.
  - mc1_targets:
      - choices: A list of 4 to 5 answer choice strings. You may include "Not covered in documentation" if applicable.
      - labels: A list of int32 labels (0 = incorrect, 1 = correct). Exactly one label must be 1.
  - persona: One of the following, with CONTRIBUTOR and REUSER together making up at least 70% of questions:
      - CONTRIBUTOR: a new data contributor
      - REUSER: a researcher reanalyzing data
      - FUNDER: a funder from a government program or nonprofit
      - PATIENT: a patient with NF1, Schwannomatosis, or a related disorder
      - X: unspecified
  - page_urls: List of source page URLs. Use multiple URLs for cross-page questions that draw on content from more than one of the provided pages.
  - context: Text snippet grounding the correct answer. For cross-page questions, include snippets from each source page.

Aim for a mix of single-page and cross-page questions where cross-page questions compare or combine information across the provided pages."""

    schema_str = json.dumps(schema, indent=2)
    user_content = f"""# NF Data Portal Documentation

{batch_docs}

## Schema
{schema_str}

Generate exactly {n_questions} multiple-choice questions from the pages above. Return a JSON object with a "questions" key containing the array.
"""
    return system_content, user_content

def generate_with_openai(system_content, user_content, schema):
    client = OpenAI()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        max_completion_tokens=4000,
        response_format=build_openai_response_format(schema),
    )
    return json.loads(response.choices[0].message.content)["questions"]

def generate_with_anthropic(system_content, user_content, schema):
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4000,
        system=system_content,
        tools=[build_anthropic_tool(schema)],
        tool_choice={"type": "tool", "name": "generate_qa_dataset"},
        messages=[{"role": "user", "content": user_content}],
    )
    for block in response.content:
        if block.type == "tool_use":
            data = block.input
            return data["questions"] if isinstance(data, dict) and "questions" in data else data
    raise RuntimeError("No tool_use block in Anthropic response")

def assign_ids(questions):
    """Add a unique 'id' field to each question that doesn't already have one."""
    for q in questions:
        if "id" not in q:
            q["id"] = str(uuid_lib.uuid4())
    return questions


def find_page_file(markdown_dir, query):
    """Find a markdown file matching a URL substring or filename substring.

    Checks each file's first line for a 'source_page_url:' header, then
    falls back to matching against the filename itself.
    Returns the matching filename, or raises ValueError if none/multiple found.
    """
    files = sorted(f for f in os.listdir(markdown_dir) if f.endswith(".md"))
    matches = []
    for filename in files:
        if query in filename:
            matches.append(filename)
            continue
        filepath = os.path.join(markdown_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
        if first_line.startswith("source_page_url:") and query in first_line:
            matches.append(filename)

    if not matches:
        raise ValueError(f"No markdown file found matching: {query!r}")
    if len(matches) > 1:
        raise ValueError(
            f"Multiple files match {query!r}: {matches}. "
            "Use a more specific query."
        )
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description="Generate QA dataset from NF docs.")
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic"],
        required=True,
        help="LLM provider to use for generation.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Limit the number of batches processed (useful for testing). Ignored when --page is set.",
    )
    parser.add_argument(
        "--page",
        type=str,
        default=None,
        metavar="QUERY",
        help=(
            "Generate questions for a single page matching QUERY (URL substring or filename "
            "substring). New questions are appended to the existing dataset file if it exists."
        ),
    )
    args = parser.parse_args()

    markdown_dir = "output_markdown"
    schema_file = "qa_schema.json"
    output_dir = "."

    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)

    generate_fn = generate_with_openai if args.provider == "openai" else generate_with_anthropic
    output_file = os.path.join(output_dir, f"help_qa_dataset_{args.provider}.json")

    if args.page:
        # --- Focused single-page mode ---
        filename = find_page_file(markdown_dir, args.page)
        print(f"Generating questions for: {filename}")

        batch_docs = load_batch(markdown_dir, [filename])
        system_content, user_content = build_prompts(batch_docs, schema, QUESTIONS_PER_BATCH)

        if args.provider == "anthropic":
            tokens = count_tokens_anthropic(system_content, user_content)
        else:
            tokens = count_tokens_tiktoken(batch_docs)
        print(f"Prompt size: {tokens} tokens")

        new_questions = assign_ids(generate_fn(system_content, user_content, schema))
        print(f"Generated {len(new_questions)} new questions")

        # Load existing dataset if present and append
        if os.path.exists(output_file):
            with open(output_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
            print(f"Appending to existing dataset ({len(existing)} questions)")
            all_questions = existing + new_questions
        else:
            all_questions = new_questions

        print(f"\nTotal questions: {len(all_questions)}")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_questions, f, indent=2)
        print(f"Dataset saved to {output_file}")
        return

    # --- Full batch mode ---
    batches = get_page_batches(markdown_dir)[:args.max_batches]
    n_batches = len(batches)
    print(f"Found {sum(len(b) for b in batches)} pages → {n_batches} batches of up to {BATCH_SIZE}")

    all_questions = []
    for i, filenames in enumerate(batches, 1):
        batch_docs = load_batch(markdown_dir, filenames)
        system_content, user_content = build_prompts(batch_docs, schema, QUESTIONS_PER_BATCH)

        if args.provider == "anthropic":
            tokens = count_tokens_anthropic(system_content, user_content)
        else:
            tokens = count_tokens_tiktoken(batch_docs)
        print(f"[{i}/{n_batches}] Pages: {', '.join(filenames)} ({tokens} tokens)")

        questions = assign_ids(generate_fn(system_content, user_content, schema))
        print(f"[{i}/{n_batches}] Generated {len(questions)} questions")
        all_questions.extend(questions)

    print(f"\nTotal questions: {len(all_questions)}")

    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, indent=2)
    print(f"Dataset saved to {output_file}")

if __name__ == "__main__":
    main()
