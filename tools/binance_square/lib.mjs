import fs from "fs";
import os from "os";
import path from "path";

const BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi";
const BASE_URL_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi";
const CONFIG_FILE = path.join(os.homedir(), ".config", "binance-square", "openapi-key");
const POLL_INTERVAL_MS = 3000;
const MAX_POLL_RETRIES = 10;
const CONTENT_TYPE_MAP = {
  jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", gif: "image/gif",
  webp: "image/webp", mp4: "video/mp4", mov: "video/quicktime",
};

export function readSavedApiKey() {
  if (!fs.existsSync(CONFIG_FILE)) return "";
  return fs.readFileSync(CONFIG_FILE, "utf8").trim();
}

export function resolveApiKey(args = []) {
  if (args.includes("--key")) {
    throw new Error("Do not pass API keys with --key. Set BINANCE_SQUARE_OPENAPI_KEY instead.");
  }
  const envKey = process.env.BINANCE_SQUARE_OPENAPI_KEY;
  if (envKey?.trim()) return envKey.trim();
  const savedKey = readSavedApiKey();
  if (savedKey) return savedKey;
  throw new Error("Missing Square OpenAPI key. Set BINANCE_SQUARE_OPENAPI_KEY.");
}

export async function api(endpoint, apiKey, body, baseUrl = BASE_URL_V2) {
  const res = await fetch(`${baseUrl}${endpoint}`, {
    method: "POST",
    headers: {
      "X-Square-OpenAPI-Key": apiKey,
      "Content-Type": "application/json",
      clienttype: "binanceSkill",
    },
    body: JSON.stringify(body),
  });
  const raw = await res.text();

  if (endpoint === "/content/add" && res.status === 504) {
    return { id: null, shareLink: null, publishStatus: "success_without_post_id" };
  }

  let json;
  try {
    json = JSON.parse(raw);
  } catch {
    throw new Error(`API returned non-JSON response: ${res.status} ${res.statusText}`);
  }
  if (json.code !== "000000") {
    throw new Error(`API error [${json.code}]: ${json.message}`);
  }
  return json.data;
}

export async function publish(apiKey, body) {
  return await api("/content/add", apiKey, body, BASE_URL_V1);
}

export function getContentType(filePath) {
  const ext = path.extname(filePath).slice(1).toLowerCase();
  return CONTENT_TYPE_MAP[ext] || "application/octet-stream";
}

async function uploadToS3(presignedUrl, filePath, contentType) {
  const fileBuffer = fs.readFileSync(filePath);
  const res = await fetch(presignedUrl, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: fileBuffer,
  });
  if (!res.ok) throw new Error(`S3 upload failed: ${res.status} ${res.statusText}`);
}

async function pollImageStatus(apiKey, fileTicket) {
  for (let i = 0; i < MAX_POLL_RETRIES; i++) {
    const data = await api("/image/imageStatus", apiKey, { fileTicket });
    if (data.status === 1) return data;
    if (data.status === 2) throw new Error(`Processing failed: ${data.failedReason}`);
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error(`Image processing timed out after ${MAX_POLL_RETRIES} retries`);
}

export async function uploadImage(apiKey, filePath) {
  const imageName = path.basename(filePath);
  const contentType = getContentType(filePath);
  const { presignedUrl, fileTicket } = await api(
    "/image/presignedUrl",
    apiKey,
    { imageName },
  );
  await uploadToS3(presignedUrl, filePath, contentType);
  const status = await pollImageStatus(apiKey, fileTicket);
  return status.imageUrl;
}

export function printPublishSuccess(result) {
  console.log("Success!");
  console.log(`ID: ${result.id ?? "unavailable"}`);
  console.log(`Link: ${result.shareLink ?? "unavailable"}`);
}
