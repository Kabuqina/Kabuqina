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
    `kabuqina-api-mode-${path.basename(relativePath, ".ts")}-${process.pid}-${Date.now()}.mjs`,
  );
  fs.writeFileSync(tempPath, compiled, "utf8");
  try {
    return await import(pathToFileURL(tempPath).href);
  } finally {
    fs.rmSync(tempPath, { force: true });
  }
}

const {
  inferApiMode,
  normalizeApiBaseUrl,
  persistedApiMode,
  shouldProbeOpenAiModels,
} = await importTs("./api-mode.ts");

assert.equal(inferApiMode("custom", "https://example.com/v1"), "chat_completions");
assert.equal(
  inferApiMode("custom", "https://example.com/anthropic/"),
  "anthropic_messages",
);
assert.equal(
  inferApiMode("anthropic", "https://proxy.example.com"),
  "anthropic_messages",
);
assert.equal(
  inferApiMode("custom", "https://api.kimi.com/coding"),
  "anthropic_messages",
);
assert.equal(
  normalizeApiBaseUrl(" https://example.com/anthropic/// "),
  "https://example.com/anthropic",
);
assert.equal(persistedApiMode("auto"), null);
assert.equal(persistedApiMode("chat_completions"), "chat_completions");
assert.equal(persistedApiMode("anthropic_messages"), "anthropic_messages");
assert.equal(
  shouldProbeOpenAiModels("auto", "custom", "https://example.com/anthropic"),
  false,
);
assert.equal(
  shouldProbeOpenAiModels("anthropic_messages", "custom", "https://example.com/v1"),
  false,
);
assert.equal(
  shouldProbeOpenAiModels("chat_completions", "custom", "https://example.com/v1"),
  true,
);
assert.equal(
  shouldProbeOpenAiModels("auto", "custom", "https://example.com/v1"),
  true,
);

const llmConfigSource = fs.readFileSync(new URL("./llm-config.ts", import.meta.url), "utf8");
assert.match(llmConfigSource, /apiMode:\s*ApiMode\s*\|\s*null/);
assert.match(llmConfigSource, /api_mode:\s*ApiMode\s*\|\s*null/);
