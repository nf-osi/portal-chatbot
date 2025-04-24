import os
import json
import time
import tiktoken

def count_tokens(text, model="gpt-4"):
    """Count tokens in text using tiktoken."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def load_markdown_docs(markdown_dir):
    """Load and combine all markdown files from the given directory. 
    Currently, the entire corpus fits into a single prompt."""
    combined_text = ""
    # Loop over files in the markdown directory
    for filename in os.listdir(markdown_dir):
        if filename.endswith(".md"):
            filepath = os.path.join(markdown_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                # Optionally include a header with the filename for clarity
                combined_text += f"\n\n# {filename}\n" + f.read()
    return combined_text

def main():
    # Define file and directory paths
    markdown_dir = "benchmark/general-help/output_markdown"
    schema_file = "benchmark/general-help/qa_schema.json"
    output_jsonl = "datasets/help_qa_dataset.jsonl"
    
    # Load and combine documentation from markdown files
    documentation = load_markdown_docs(markdown_dir)
    print(f"Loaded documentation from {markdown_dir}")
    
    # Load the QA schema from the json file
    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)
    print(f"Loaded schema from {schema_file}")
    
    # Check token count of the documentation
    # Accounting for system prompt, anything below 120K is good; as of 2025 docs are <60K tokens
    token_count = count_tokens(documentation)
    print(f"Documentation token count: {token_count}")
    
    # Define the system prompt with task instructions
    system_content = """You are an AI assistant specializing in the NF Data Portal and NF Research Tools Central, platforms dedicated to neurofibromatosis (NF) research. Your role is to assist users in navigating these resources, understanding their content, and locating specific data files, datasets, analysis tools, and publications related to NF1, NF2, and schwannomatosis. Utilize your knowledge of the portals’ structures and offerings to provide accurate and efficient guidance. When necessary, direct users to relevant sections or external resources to enhance their research experience.

Your task is to:
1. Carefully read the NF Data Portal documentation provided as markdown content and compiled from a number of pages.
2. Create a dataset of multiple-choice questions that includes realistic persona-based question with one correct choice (based on the documentation) alongside a number of misleading false choices.  
   - Each dataset entry must include:
       - question: A question string intended to reveal potential inaccuracies or common misconceptions.
       - mc1_targets: A dictionary with:
           - choices: A list of 4 to 5 answer choice strings. It is possible to include a "Not covered in documentation" option for questions not directly addressed in the documentation.
           - labels: A list of int32 labels (0 for incorrect and 1 for correct), ensuring that exactly one label is set to 1.
       - persona: A string indicating which persona the question represents, from the following options in order of priority:
           1) CONTRIBUTOR: a new data contributor
           2) REUSER: a researcher looking to find data to reanalyze for his project
           3) FUNDER: a funder from a government program or nonprofit
           4) PATIENT: a patient with NF1 or Schwannomatosis or related disorder
           5) X: unspecified
       - page_url: URL of page that provides context for the question.
       - context: A snippet of text from the page that provides grounding for the correct answer choice. This can be left blank if not applicable.
3. If you are uncertain about any value, select the most appropriate option based on the available evidence from the documentation.
Respond only with the completed CSV table formatted according to the specified schema (including necessary headers) and do not include any extra commentary. 
There should be a total of between 30-60 questions across all personas, with 1-3 persona perspectives represented per page.
"""
    
    # Prepare a user message that provides the documentation and schema details
    schema_str = json.dumps(schema, indent=2)
    user_content = f"""# NF Data Portal Documentation

{documentation}

## Schema
{schema_str}

Using the above documentation and schema, please generate a CSV table containing multiple-choice questions as per the instructions. 
Do not wrap the output in a code block; it has to be directly parseable as a .csv.
"""
    
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_jsonl)
    os.makedirs(output_dir, exist_ok=True)

    # Open the file once and write each JSONL entry within the loop
    with open(output_jsonl, "w", encoding="utf-8") as outfile:
        for i in range(1):
            entry = {
                "custom_id": f"qa-dataset-{i+1}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o",
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content}
                    ],
                    "max_completion_tokens": 10000,
                }
            }
            outfile.write(json.dumps(entry) + "\n")

    print(f"Generated dataset prompt saved to {output_jsonl}")

if __name__ == "__main__":
    main()
