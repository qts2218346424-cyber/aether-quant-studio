#!/usr/bin/env node

import { parseArgs } from "node:util";
import {
  printPublishSuccess,
  publish,
  resolveApiKey,
  uploadImage,
} from "./lib.mjs";

const { values } = parseArgs({
  options: {
    text: { type: "string" },
    title: { type: "string" },
    cover: { type: "string" },
    images: { type: "string" },
    sentiment: { type: "string" },
    symbol: { type: "string" },
    help: { type: "boolean", short: "h" },
  },
  strict: false,
});

if (values.help) {
  console.log(`Usage:
  node post-image.mjs --text <content> [--title <title>] [--cover <path>] [--images <p1,p2...>] [--sentiment BULLISH|BEARISH]

Options:
  --text <content>      Post or article text content (required)
  --title <title>       Article title. When present, publishes as contentType=2 (article)
  --cover <path>        Cover image path (16:9 recommended)
  --images <paths>      Comma-separated list of image paths to attach (max 4)
  --sentiment <type>    BULLISH or BEARISH indicator`);
  process.exit(0);
}

if (!values.text?.trim()) {
  console.error("Error: --text is required");
  process.exit(1);
}

try {
  const key = resolveApiKey(process.argv.slice(2));
  const isArticle = Boolean(values.title?.trim());
  let coverUrl = null;
  const uploadedImages = [];

  // 1. 处理 --cover
  if (values.cover?.trim()) {
    coverUrl = await uploadImage(key, values.cover.trim());
    console.log("Cover uploaded.");
  }

  // 2. 处理 --images (最多 4 张图片)
  if (values.images?.trim()) {
    const rawPaths = values.images.split(",").map((p) => p.trim()).filter(Boolean);
    const paths = rawPaths.slice(0, 4);
    for (const p of paths) {
      const url = await uploadImage(key, p);
      uploadedImages.push(url);
    }
    if (uploadedImages.length > 0) {
      console.log(`Images uploaded: ${uploadedImages.length}.`);
    }
  }

  // 3. 规范正文：去除可能残留的超长 base64 字符串，保留文字图注
  const cleanText = values.text
    .replace(/!\[([^\]]*)\]\(data:image\/[^)]+\)/g, (m, caption) => caption ? `【${caption}】` : "")
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, (m, caption) => caption ? `【${caption}】` : "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  const payload = {
    contentType: isArticle ? 2 : 1,
    bodyTextOnly: cleanText,
  };

  if (isArticle) {
    payload.title = values.title.trim();
    // 文章模式：优先使用 coverUrl，若未传 cover 则使用第一张 image
    payload.cover = coverUrl || (uploadedImages.length > 0 ? uploadedImages[0] : null);
    if (!payload.cover) {
      console.error("Error: Article posts with --title require a --cover image or at least one --images image");
      process.exit(1);
    }
    // 附加图片列表（供详情展开或多图排版）
    if (uploadedImages.length > 0) {
      payload.imageList = uploadedImages;
    }
  } else {
    // 动态模式：使用 imageList（最多4张直显）
    const allImages = [];
    if (coverUrl) allImages.push(coverUrl);
    for (const img of uploadedImages) {
      if (!allImages.includes(img)) allImages.push(img);
    }
    if (allImages.length === 0) {
      console.error("Error: Short image post requires at least one image via --cover or --images");
      process.exit(1);
    }
    payload.imageList = allImages.slice(0, 4);
  }

  if (values.symbol?.trim()) {
    const sym = values.symbol.trim().toUpperCase();
    payload.symbol = sym;
    payload.symbols = [sym];
  }

  if (values.sentiment) {
    const sentUpper = values.sentiment.toUpperCase();
    payload.sentiment = sentUpper;
    payload.sentimentType = sentUpper === "BULLISH" ? 1 : 2;
  }

  const result = await publish(key, payload);
  console.log("Article submitted.");
  printPublishSuccess(result);
} catch (err) {
  console.error(`Failed: ${err.message}`);
  process.exit(1);
}
