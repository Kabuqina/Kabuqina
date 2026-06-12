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
const providerIds = PROVIDERS.map((provider) => provider.id);

for (const id of ["alibaba", "zai", "kimi-coding", "kimi-coding-cn", "minimax-cn"]) {
  assert.ok(providerIds.includes(id), `Provider dropdown metadata should include Hermes provider ${id}.`);
}

const getAccessPassSource = fs.readFileSync(new URL("./steps/GetAccessPass.tsx", import.meta.url), "utf8");

assert.match(
  getAccessPassSource,
  /customProviderId/,
  "Custom provider mode should expose state for a manually entered provider id.",
);

assert.match(
  getAccessPassSource,
  /providerForSave[\s\S]*customProviderId\.trim\(\)\s*\|\|\s*"custom"[\s\S]*provider:\s*providerForSave/,
  "Saving the custom option should persist the user-entered provider id when provided.",
);

assert.match(
  getAccessPassSource,
  /savedProviderMatchesSelection[\s\S]*preview\.provider === provider\.id[\s\S]*preview\.provider === dropdownProvider[\s\S]*preview\.provider === \(customProviderId\.trim\(\) \|\| "custom"\)/,
  "Saved access-pass state should only be reused when it matches the selected provider.",
);

assert.match(
  getAccessPassSource,
  /if \(!savedProviderMatchesSelection \|\| !isCustom \|\| !saved\) return;/,
  "Custom onboarding should not prefill DeepSeek or other saved provider details.",
);

assert.match(
  getAccessPassSource,
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
assert.match(stringsSource, /skipTitle:\s*"跳过"/);
assert.match(stringsSource, /skipTitle:\s*"Skip"/);

const settingsGatewaySource = fs.readFileSync(new URL("../advanced/settings/SettingsGateway.tsx", import.meta.url), "utf8");
const expectedGatewayLabels = ["飞书", "QQ", "微信", "企微"];
for (const label of expectedGatewayLabels) {
  assert.match(settingsGatewaySource, new RegExp(`label:\\s*"${label}"`));
}
const gatewayCatalogSource = optionDataSource.match(/export const CATALOG_GATEWAY[\s\S]*?export const CATALOG_TOOLS/)?.[0] ?? "";
const gatewayLabels = [...gatewayCatalogSource.matchAll(/name:\s*L\("([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(gatewayLabels, expectedGatewayLabels);
