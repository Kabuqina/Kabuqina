import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import ts from "typescript";

async function importTsBundle(entryRelativePath, dependencyRelativePaths = []) {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "kabuqina-export-"));
  const compile = (relativePath) => {
    const sourcePath = new URL(relativePath, import.meta.url);
    const source = fs.readFileSync(sourcePath, "utf8");
    const compiled = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.ES2022,
        target: ts.ScriptTarget.ES2022,
        verbatimModuleSyntax: true,
      },
    }).outputText.replace(/from "\.\/([^"]+)";/g, 'from "./$1.mjs";');
    const outName = `${path.basename(relativePath, ".ts")}.mjs`;
    fs.writeFileSync(path.join(tempDir, outName), compiled, "utf8");
    return outName;
  };

  for (const dep of dependencyRelativePaths) {
    compile(dep);
  }
  const entryName = compile(entryRelativePath);
  try {
    return await import(pathToFileURL(path.join(tempDir, entryName)).href);
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true });
  }
}

const {
  rowsToExportDialogue,
  buildExportMarkdown,
  buildExportJson,
  exportLabelsForLocale,
  defaultExportFilename,
} = await importTsBundle("./chatExport.ts", ["./deskUserContent.ts"]);

const { DESK_UI_PERSIST_PREFIX } = await importTsBundle("./deskUserContent.ts");

const labels = exportLabelsForLocale("zh");

assert.deepEqual(
  rowsToExportDialogue(
    [
      {
        role: "user",
        content: `${DESK_UI_PERSIST_PREFIX}{"text":"帮我看这份 PDF","attachments":[]}`,
        timestamp: 1_700_000_000,
      },
      { role: "assistant", content: "好的，我先打开看看。", timestamp: 1_700_000_100 },
      { role: "tool", content: '{"ok":true}', timestamp: 1_700_000_200 },
    ],
    labels,
  ),
  [
    {
      role: "user",
      speaker: "用户",
      text: "帮我看这份 PDF",
      attachments: undefined,
      timestamp: 1_700_000_000,
    },
    {
      role: "assistant",
      speaker: "卡布奇娜",
      text: "好的，我先打开看看。",
      timestamp: 1_700_000_100,
    },
  ],
  "Export dialogue should include parsed user turns and hide tool rows.",
);

const md = buildExportMarkdown(
  [{ id: "sess-1", title: "PDF 帮助", model: "deepseek-v4-flash" }],
  new Map([
    [
      "sess-1",
      [
        { role: "user", content: "你好", timestamp: 1_700_000_000 },
        { role: "assistant", content: "你好呀", timestamp: 1_700_000_100 },
      ],
    ],
  ]),
  labels,
  "zh",
);

assert.match(md, /### 👤 用户[\s\S]*你好/);
assert.match(md, /### 🤖 卡布奇娜[\s\S]*你好呀/);
assert.doesNotMatch(md, /Hermes|hermesdesk|HermesDesk/i);

const json = JSON.parse(
  buildExportJson(
    [{ id: "sess-1", title: "PDF 帮助", model: "deepseek-v4-flash" }],
    new Map([
      [
        "sess-1",
        [
          { role: "user", content: "你好", timestamp: 1_700_000_000 },
          { role: "assistant", content: "你好呀", timestamp: 1_700_000_100 },
        ],
      ],
    ]),
    labels,
    "zh",
  ),
);

assert.equal(json.app, "卡布奇娜");
assert.equal(json.sessions[0].dialogue[0].speaker, "用户");
assert.equal(json.sessions[0].dialogue[1].speaker, "卡布奇娜");
assert.equal(defaultExportFilename("json"), "kabuqina-chat-export.json");
assert.equal(defaultExportFilename("markdown"), "kabuqina-chat-export.md");

const exportPageSource = fs.readFileSync(new URL("../advanced/Export.tsx", import.meta.url), "utf8");
assert.match(exportPageSource, /chatExport/);
assert.doesNotMatch(exportPageSource, /hermesdesk-export|🤖 Hermes/i);
