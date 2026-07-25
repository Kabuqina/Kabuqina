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
const mainSource = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");
const gatewayRegistrySource = fs.readFileSync(
  new URL("../lib/gatewayPlatformSettingsRegistry.ts", import.meta.url),
  "utf8",
);
const configModalSource = fs.readFileSync(
  new URL("../onboarding/components/ConfigModalBody.tsx", import.meta.url),
  "utf8",
);
const platformEnvStatusSource = fs.readFileSync(
  new URL("../onboarding/hooks/usePlatformEnvStatus.ts", import.meta.url),
  "utf8",
);
const localeStringsSource = fs.readFileSync(
  new URL("../locales/strings.ts", import.meta.url),
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
  /platformItems\s*=\s*\[[\s\S]*qqbot[\s\S]*weixin[\s\S]*dingtalk[\s\S]*telegram[\s\S]*whatsapp[\s\S]*email[\s\S]*\]/,
  "Messaging platform settings should contain the exact retained entries for both profiles.",
);

assert.doesNotMatch(
  settingsGatewaySource,
  /platformItems\s*=\s*\[[\s\S]*(feishu|wecom|discord|slack)[\s\S]*\]/i,
  "Gateway navigation must not contain removed platform entries.",
);

assert.doesNotMatch(
  mainSource,
  /FeishuPage|settings\/feishu/,
  "The removed Feishu settings route must not remain reachable.",
);

for (const [source, label] of [
  [gatewayRegistrySource, "gateway settings registry"],
  [configModalSource, "onboarding config modal"],
  [platformEnvStatusSource, "onboarding env-status hook"],
  [localeStringsSource, "visible locale copy"],
]) {
  assert.doesNotMatch(
    source,
    /feishu|飞书|lark|FEISHU_/i,
    `The ${label} must not expose Feishu configuration or commands.`,
  );
}

assert.doesNotMatch(
  gatewayRegistrySource,
  /SMS_HOME_CHANNEL|smsHomeChannel/,
  "Email advanced settings must not expose or remove legacy SMS home data.",
);

assert.match(
  gatewayRegistrySource,
  /platform:\s*"email"[\s\S]*envKey:\s*"EMAIL_HOME_ADDRESS"/,
  "Email advanced settings should use the canonical email home address key.",
);

for (const relativePath of [
  "../components/FeishuQrRouteBlock.tsx",
  "./pages/FeishuPage.tsx",
]) {
  assert.equal(
    fs.existsSync(new URL(relativePath, import.meta.url)),
    false,
    `${relativePath} must be physically absent.`,
  );
}

assert.match(
  settingsGatewaySource,
  /platformItems\.filter\(\(\{ key \}\) => profileContract\.visibleGateways\.includes\(key\)\)/,
  "Gateway navigation should be filtered by the trusted product-profile contract.",
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
