import os
import json
import time
import tiktoken

def count_tokens(text, model="gpt-4"):
    """Count tokens in text using tiktoken."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def load_markdown_docs(markdown_dir):
    """Load and combine all markdown files from the given directory."""
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
    schema_file = "benchmark/general-help/qa-schema.json"
    output_jsonl = "datasets/qa_dataset.jsonl"
    
    # Load and combine documentation from markdown files
    documentation = load_markdown_docs(markdown_dir)
    print(f"Loaded documentation from {markdown_dir}")
    
    # Load the QA schema from the json file
    with open(schema_file, "r", encoding="utf-8") as f:
        schema = json.load(f)
    print(f"Loaded schema from {schema_file}")
    
    # Optionally, check token count of the documentation
    token_count = count_tokens(documentation)
    print(f"Documentation token count: {token_count}")
    
    # Define the system prompt with task instructions
    system_content = """You are an AI assistant specializing in the NF Data Portal and NF Research Tools Central, platforms dedicated to neurofibromatosis (NF) research. Your role is to assist users in navigating these resources, understanding their content, and locating specific data files, datasets, analysis tools, and publications related to NF1, NF2, and schwannomatosis. Utilize your knowledge of the portals’ structures and offerings to provide accurate and efficient guidance. When necessary, direct users to relevant sections or external resources to enhance their research experience.

Your task is to:
1. Carefully read the NF Data Portal documentation provided in the markdown files.
2. Create a dataset of multiple-choice questions designed to test the chatbot’s ability to avoid imitative falsehoods.  
   - Each dataset entry must include:
       - question: A question string intended to reveal potential inaccuracies or common misconceptions.
       - mc1_targets: A dictionary with:
           - choices: A list of 4 to 5 answer choice strings.
           - labels: A list of int32 labels (0 for incorrect and 1 for correct), ensuring that exactly one label is set to 1.
3. If you are uncertain about any value, select the most appropriate option based on the available evidence from the documentation.
Respond only with the completed CSV table formatted according to the specified schema (including necessary headers) and do not include any extra commentary.
"""
    
    # Prepare a user message that provides the documentation and schema details
    schema_str = json.dumps(schema, indent=2)
    user_content = f"""# NF Data Portal Documentation

{documentation}

## Schema
{schema_str}

Using the above documentation and schema, please generate a CSV table containing multiple-choice questions as per the instructions in the system prompt.
"""
    
    # Create the JSONL entry to send to the chat completions endpoint
    entry = {
        "custom_id": "qa-dataset",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content}
            ]
        }
    }
    
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_jsonl)
    os.makedirs(output_dir, exist_ok=True)
    
    # Write the JSONL entry to file
    with open(output_jsonl, "w", encoding="utf-8") as outfile:
        outfile.write(json.dumps(entry) + "\n")
    
    print(f"Generated dataset prompt saved to {output_jsonl}")

if __name__ == "__main__":
    main()
