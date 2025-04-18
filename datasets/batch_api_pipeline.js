import fs from "fs";
import OpenAI from "openai";
import path from "path";

// Initialize OpenAI client with API key from environment variables.
const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

/**
 * Returns a promise that resolves after the given delay in milliseconds.
 * @param {number} ms - Milliseconds to delay.
 */
function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function main() {
  try {
    // --- Step 0: Get the dataset file path from command line arguments
    const args = process.argv.slice(2);
    const datasetPath = args[0] || "datasets/qa_dataset.jsonl";
    
    if (!fs.existsSync(datasetPath)) {
      throw new Error(`Dataset file not found: ${datasetPath}`);
    }
    
    console.log(`Using dataset file: ${datasetPath}`);

    // --- Step 1: Upload file ---
    console.log("Uploading file...");
    const uploadResponse = await openai.files.create({
      file: fs.createReadStream(datasetPath),
      purpose: "batch",
    });
    console.log("Upload response:", uploadResponse);

    // Get the file id from the upload response.
    const inputFileId = uploadResponse.id;
    console.log("Input file id:", inputFileId);
    if (!inputFileId) {
      throw new Error("Failed to get file id from upload response.");
    }
    
    // --- Step 2: Create batch ---
    console.log("Creating batch...");
    const batchResponse = await openai.batches.create({
      input_file_id: inputFileId,
      endpoint: "/v1/chat/completions",
      completion_window: "24h"
    });
    console.log("Batch creation response:", batchResponse);
    
    // Get the batch id from the batch creation response.
    const batchId = batchResponse.id;
    console.log("Batch id:", batchId);
    if (!batchId) {
      throw new Error("Failed to get batch id from batch creation response.");
    }
    
    // --- Step 3: Poll for batch status until output_file_id is available ---
    let outputFileId = null;
    let attempts = 0;
    const maxAttempts = 144; // 144 attempts = 24 hours (6 checks per hour * 24 hours)
    while (!outputFileId && attempts < maxAttempts) {
      console.log(`Checking batch status (attempt ${attempts + 1})...`);
      const statusResponse = await openai.batches.retrieve(batchId);
      console.log("Batch status response:", statusResponse);
      
      // Check directly for output_file_id.
      outputFileId = statusResponse.output_file_id;
      if (outputFileId) {
        console.log("Output file id available:", outputFileId);
        break;
      }
      
      // Wait 10 minutes before checking again.
      await delay(600000);
      attempts++;
    }
    if (!outputFileId) {
      throw new Error("Timed out waiting for output file id in batch status.");
    }
    
    // --- Step 4: Retrieve batch result file contents ---
    console.log("Retrieving batch result file contents...");
    const fileResponse = await openai.files.content(outputFileId);
    const fileContents = await fileResponse.text();
    
    console.log("Final batch result file ID:", outputFileId);
    // If you have a file name or need to derive it from some logic, you should include it here
    // Define the directory where you want to save the output file.
    const outputDirectory = "./output";  // Change this to your desired output directory
    if (!fs.existsSync(outputDirectory)){
        fs.mkdirSync(outputDirectory);
    }

    const outputFileName = "batch_api_output.log";
    const outputFilePath = path.join(outputDirectory, outputFileName);
    console.log("Final batch result. File name:", outputFileName);
    fs.writeFileSync(outputFilePath, fileContents, 'utf8');

    
  } catch (error) {
    console.error("Error in pipeline:", error);
  }
}

main();
