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

async function getDatasetPath(args) {
  const datasetPath = args[0] || "datasets/help_qa_dataset.jsonl";
  if (!fs.existsSync(datasetPath)) {
    throw new Error(`Dataset file not found: ${datasetPath}`);
  }
  return datasetPath;
}

async function uploadFile(datasetPath) {
  console.log("Uploading file...");
  const uploadResponse = await openai.files.create({
    file: fs.createReadStream(datasetPath),
    purpose: "batch",
  });
  console.log("Upload response:", uploadResponse);

  const inputFileId = uploadResponse.id;
  console.log("Input file id:", inputFileId);
  if (!inputFileId) {
    throw new Error("Failed to get file id from upload response.");
  }
  return inputFileId;
}

async function createBatch(inputFileId) {
  console.log("Creating batch...");
  const batchResponse = await openai.batches.create({
    input_file_id: inputFileId,
    endpoint: "/v1/chat/completions",
    completion_window: "24h"
  });
  console.log("Batch creation response:", batchResponse);
  
  const batchId = batchResponse.id;
  console.log("Batch id:", batchId);
  if (!batchId) {
    throw new Error("Failed to get batch id from batch creation response.");
  }
  return batchId;
}

async function pollBatchStatus(batchId) {
  let outputFileId = null;
  let errorFileId = null;
  let attempts = 0;
  const maxAttempts = 144;
  
  while (!outputFileId && !errorFileId && attempts < maxAttempts) {
    console.log(`Checking batch status (attempt ${attempts + 1})...`);
    const statusResponse = await openai.batches.retrieve(batchId);
    console.log("Batch status response:", statusResponse);
    
    outputFileId = statusResponse.output_file_id;
    if (outputFileId) {
      console.log("Success for batch. Output file available:", outputFileId);
      break;
    }

    errorFileId = statusResponse.error_file_id;
    if (errorFileId) {
      console.log("Error for batch. Error file available:", errorFileId);
      break;
    }
    
    await delay(600000);
    attempts++;
  }
  
  if (!outputFileId && !errorFileId) {
    throw new Error("Timed out waiting for output file id in batch status.");
  }
  return outputFileId || errorFileId;
}

async function retrieveBatchResultFile(outputFileId, outputPath) {
  try {
    console.log("Retrieving batch result file contents...");
    const fileResponse = await openai.files.content(outputFileId);
    const fileContents = await fileResponse.text();

    console.log("Final batch result file ID:", outputFileId);
    console.log("Final batch result is at:", outputPath);
    fs.writeFileSync(outputPath, fileContents, 'utf8');
  } catch (error) {
    console.error("Error retrieving batch result file:", error);
    throw error;
  }
}

async function main() {
  try {
    const args = process.argv.slice(2);
    const outputPath = args[1] || "output/batch_qa_benchmark.jsonl";
    
    const datasetPath = await getDatasetPath(args);
    console.log(`Using dataset file: ${datasetPath}`);

    const inputFileId = await uploadFile(datasetPath);
    const batchId = await createBatch(inputFileId);
    const outputFileId = await pollBatchStatus(batchId);
    await retrieveBatchResultFile(outputFileId, outputPath);
  } catch (error) {
    console.error("Error in main pipeline:", error);
    throw error;
  }
}

main();