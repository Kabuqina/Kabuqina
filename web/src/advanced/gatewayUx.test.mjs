/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const platformButtonSource = fs.readFileSync(
  new URL("../components/ui/PlatformButton.tsx", import.meta.url),
  "utf8",
);
const settingsGatewaySource = fs.readFileSync(
  new URL("./settings/SettingsGateway.tsx", import.meta.url),
  "utf8",
);
const weixinSource = fs.readFileSync(
  new URL("../components/WeixinQrRouteCBlock.tsx", import.meta.url),
  "utf8",
);

assert.match(
  platformButtonSource,
  /primary:[\s\S]*kq-btn-primary/,
  "Messaging platform primary buttons should use the Kabuqina lavender primary style.",
);

assert.doesNotMatch(
  platformButtonSource,
  /primary:[\s\S]*bg-zinc-900[\s\S]*dark:bg-zinc-100/,
  "Messaging platform primary buttons should not use black-white contrast.",
);

assert.match(
  platformButtonSource,
  /secondary:[\s\S]*kq-btn-secondary/,
  "Messaging platform default buttons should use the Kabuqina frosted secondary style.",
);

assert.match(
  settingsGatewaySource,
  /platformItems\s*=\s*\[[\s\S]*feishu[\s\S]*qq[\s\S]*weixin[\s\S]*wecom[\s\S]*\]/,
  "Messaging platform settings should expose the mainland profile entries.",
);

assert.doesNotMatch(
  settingsGatewaySource,
  /platformItems\s*=\s*\[[\s\S]*(email|dingtalk)[\s\S]*\]/i,
  "Mainland profile gateway navigation should not expose Email or DingTalk.",
);

assert.match(
  settingsGatewaySource,
  /gateway-platform-nav[\s\S]*kq-btn-secondary/,
  "Messaging platform page buttons should use the Kabuqina navigation style.",
);

assert.doesNotMatch(
  settingsGatewaySource,
  /gatewayAuto|<Toggle|autoStartGateway|onToggleAutoStart/,
  "Messaging gateway settings should stay manual-start only and not expose an auto-start toggle.",
);

assert.match(
  weixinSource,
  /<PlatformButton[\s\S]*manualRestartAssistant/,
  "WeChat restart action should use the shared messaging platform button style.",
);
