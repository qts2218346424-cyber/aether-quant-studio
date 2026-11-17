#!/usr/bin/env node

import { parseArgs } from "node:util";
import { printPublishSuccess, publish, resolveApiKey } from "./lib.mjs";

const { values } = parseArgs({
  options: {
    text: { type: "string" },
    title: { type: "string" },
    help: { type: "boolean", short: "h" },
  },
  strict: true,
});

if (values.help) {
  console.log("Usage: node post-text.mjs --text <content> [--title <title>]");
  process.exit(0);
}

if (!values.text?.trim()) {
  console.error("Error: --text is required");
  process.exit(1);
}

try {
  const key = resolveApiKey(process.argv.slice(2));
  const body = {
    contentType: values.title?.trim() ? 2 : 1,
    bodyTextOnly: values.text,
  };
  if (values.title?.trim()) body.title = values.title;
  const result = await publish(key, body);
  printPublishSuccess(result);
} catch (err) {
  console.error(`Failed: ${err.message}`);
  process.exit(1);
}
