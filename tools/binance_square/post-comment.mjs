#!/usr/bin/env node
/**
 * post-comment.mjs — 在币安广场指定帖子下发布评论
 * Usage:
 *   node post-comment.mjs --post-id <postId> --text "评论内容"
 *
 * 环境变量: BINANCE_SQUARE_OPENAPI_KEY
 */
import { resolveApiKey, api } from "./lib.mjs";

process.env.NODE_USE_ENV_PROXY = "1";   // 支持系统代理

const args = process.argv.slice(2);

function getArg(flag) {
  const idx = args.indexOf(flag);
  return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : null;
}

const postId  = getArg("--post-id");
const text    = getArg("--text");

if (!postId || !text) {
  console.error("Usage: node post-comment.mjs --post-id <id> --text <comment>");
  process.exit(1);
}

const apiKey = resolveApiKey(args);

try {
  // Binance Square OpenAPI V1 评论接口
  const data = await api(
    "/comment/add",
    apiKey,
    {
      contentId: postId,
      text: text,
    },
    "https://www.binance.com/bapi/composite/v1/public/pgc/openApi",
  );

  const commentId = data?.id ?? data?.commentId ?? null;
  console.log("Comment posted successfully!");
  console.log(`Comment ID: ${commentId ?? "unavailable"}`);
  console.log(`Post ID: ${postId}`);
} catch (err) {
  // 如果评论 API 不支持（非所有账号开放），优雅降级输出警告
  if (err.message && err.message.includes("000001")) {
    console.warn(`[Warning] Comment API not available for this account: ${err.message}`);
    console.log("Comment ID: unavailable");
    process.exit(0);  // 非致命错误，允许上层继续
  }
  console.error(`Error posting comment: ${err.message}`);
  process.exit(1);
}
