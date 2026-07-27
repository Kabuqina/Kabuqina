/* global URL, process */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import ts from "typescript";

async function importTs(relativePath) {
  const sourcePath = new URL(relativePath, import.meta.url);
  const source = fs.readFileSync(sourcePath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
  }).outputText;
  const tempPath = path.join(
    os.tmpdir(),
    `kabuqina-provider-ux-${path.basename(relativePath, ".ts")}-${process.pid}-${Date.now()}.mjs`,
  );
  fs.writeFileSync(tempPath, compiled, "utf8");
  try {
    return await import(pathToFileURL(tempPath).href);
  } finally {
    fs.rmSync(tempPath, { force: true });
  }
}

const { PROVIDERS } = await importTs("../lib/providers.ts");
const { PROVIDER_PRESETS, SELECTABLE_LLM_PROVIDERS } = await importTs("../lib/llm-config.ts");
const providerIds = PROVIDERS.map((provider) => provider.id);

for (const id of ["alibaba", "zai", "kimi-coding", "kimi-coding-cn", "minimax-cn"]) {
  assert.ok(providerIds.includes(id), `Provider dropdown metadata should include Hermes provider ${id}.`);
  assert.ok(
    SELECTABLE_LLM_PROVIDERS.includes(id),
    `Shared LLM provider picker should expose Hermes provider ${id}.`,
  );
}

assert.equal(PROVIDER_PRESETS["kimi-coding-cn"].host, "https://api.kimi.com/coding/v1");

const getAccessPassSource = fs.readFileSync(new URL("./steps/GetAccessPass.tsx", import.meta.url), "utf8");
const settingsLlmConfigSource = fs.readFileSync(new URL("../advanced/settings/SettingsLlmConfig.tsx", import.meta.url), "utf8");
const llmConfigEditorSource = fs.readFileSync(new URL("../components/LlmConfigEditor.tsx", import.meta.url), "utf8");
const llmConfigSource = fs.readFileSync(new URL("../lib/llm-config.ts", import.meta.url), "utf8");

assert.match(
  getAccessPassSource,
  /LlmConfigEditor/,
  "Onboarding access-pass step should use the shared LLM config editor.",
);

assert.match(
  getAccessPassSource,
  /renderActions=\{\(\{ onSave, disabled, label \}\) =>/,
  "Onboarding access-pass actions should be rendered in the page footer.",
);

assert.match(
  getAccessPassSource,
  /WizardFooter[\s\S]*WizardFooterActions[\s\S]*onClick=\{onSave\}/,
  "Onboarding back and continue buttons should share one wizard footer.",
);

assert.match(
  settingsLlmConfigSource,
  /LlmConfigEditor/,
  "Settings model tab should use the shared LLM config editor.",
);

assert.match(
  llmConfigEditorSource,
  /settings\.llmConfigModel[\s\S]*value=\{modelId\}[\s\S]*onChange=\{\(e\) => \{\s*setModelId/,
  "The shared LLM config editor should expose an editable model field.",
);

assert.doesNotMatch(
  llmConfigEditorSource,
  /readOnly=\{!isManualCustom && hasPreset\(selectedProvider\)\}/,
  "Preset provider model fields must remain editable.",
);

assert.doesNotMatch(
  getAccessPassSource,
  /const PROVIDER_PRESETS/,
  "Provider presets should live in the shared LLM config module, not the onboarding step.",
);

assert.match(
  llmConfigEditorSource,
  /customProviderId/,
  "Custom provider mode should expose state for a manually entered provider id.",
);

assert.match(
  llmConfigEditorSource,
  /providerForSave[\s\S]*customProviderId\.trim\(\)\s*\|\|\s*"custom"[\s\S]*provider:\s*providerForSave/,
  "Saving the custom option should persist the user-entered provider id when provided.",
);

assert.match(
  llmConfigEditorSource,
  /savedProviderMatchesSelection[\s\S]*preview\.provider === selectedProvider[\s\S]*preview\.provider === \(customProviderId\.trim\(\) \|\| "custom"\)/,
  "Saved access-pass state should only be reused when it matches the selected provider.",
);

assert.match(
  llmConfigEditorSource,
  /mode === "settings"[\s\S]*setSelectedProvider/,
  "Settings mode should hydrate provider fields from saved config.",
);

assert.match(
  llmConfigEditorSource,
  /mode === "onboarding" && initialProviderId === "custom"[\s\S]*setSelectedProvider/,
  "Custom onboarding should hydrate provider fields from saved config.",
);

assert.match(
  llmConfigEditorSource,
  /apiModeSelection/,
  "The shared editor should track the API mode selection.",
);
assert.match(
  llmConfigEditorSource,
  /<details[\s\S]*apiModeAuto[\s\S]*apiModeAnthropic/,
  "The API mode override should remain inside an advanced disclosure.",
);
assert.match(
  llmConfigEditorSource,
  /api_mode:\s*persistedApiMode\(apiModeSelection\)/,
  "The editor should serialize only concrete API mode overrides.",
);
assert.match(
  llmConfigEditorSource,
  /p\.apiMode\s*\?\?\s*"auto"/,
  "Missing persisted API mode should hydrate as Automatic.",
);

assert.match(
  llmConfigSource,
  /"kimi-coding-cn":\s*\{\s*host:\s*"https:\/\/api\.kimi\.com\/coding\/v1"/,
  "Kimi / Moonshot (China) should use the current Kimi Coding base URL.",
);

assert.doesNotMatch(getAccessPassSource, /Deepseek API Key|自定义AI模型/);
assert.match(getAccessPassSource, /hd-wizard-title[\s\S]*t\("pass\.title"\)/);

const shellFrameSource = fs.readFileSync(new URL("./ShellFrame.tsx", import.meta.url), "utf8");
const indexCssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");
assert.match(shellFrameSource, /onboarding\.progress/);
assert.match(shellFrameSource, /hd-wizard-progress/);
assert.match(indexCssSource, /\.hd-wizard-title/);
assert.match(indexCssSource, /\.hd-wizard-lead/);

const wizardSource = fs.readFileSync(new URL("./Wizard.tsx", import.meta.url), "utf8");
const welcomeSource = fs.readFileSync(new URL("./steps/Welcome.tsx", import.meta.url), "utf8");
const flowConfigSource = fs.readFileSync(new URL("./flowConfig.ts", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");
const optionDataSource = fs.readFileSync(new URL("./setupCatalog/optionData.ts", import.meta.url), "utf8");

assert.doesNotMatch(wizardSource, /SetupMode|path="mode"/);
assert.match(welcomeSource, /updateDraft\(\{\s*setupMode:\s*"quick"[\s\S]*useRecommendedDefaults:\s*true/);
assert.match(welcomeSource, /nav\("\/onboarding\/brain"\)/);
assert.doesNotMatch(flowConfigSource, /FULL_STEPS|setupMode === "full"|stepToPath\("tts"\)/);
assert.doesNotMatch(stringsSource, /setupMode:|Full setup|设置方式|仔细一点/);
// gateway 段专用的"跳过"文案随 CTL-C08 一起删了；保留的是"保持默认"这一支。
assert.match(stringsSource, /skipKeepTitle:/);
assert.doesNotMatch(stringsSource, /skipTitle:/);

// 移动端 Bot 与邮件渠道的产品面已移除（CTL-C08）：onboarding 不再有 gateway 段，
// 首轮引导以 pass 收尾。这里改为负向断言，防止渠道配置悄悄回流到首次运行。
assert.doesNotMatch(optionDataSource, /CATALOG_GATEWAY|gatewayCatalogFor/);
assert.doesNotMatch(optionDataSource, /DINGTALK_CLIENT_ID|TELEGRAM_BOT_TOKEN|EMAIL_IMAP_HOST|WHATSAPP_ENABLED/);
assert.doesNotMatch(flowConfigSource, /"gateway"/);
assert.doesNotMatch(wizardSource, /path="gateway"/);
assert.match(flowConfigSource, /return "\/chat";/);
