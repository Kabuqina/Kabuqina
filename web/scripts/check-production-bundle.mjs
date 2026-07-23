// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { readdir, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const assetsDir = resolve(scriptDir, "..", "dist", "assets");
const entries = await readdir(assetsDir, { withFileTypes: true });
const javascriptFiles = entries
  .filter((entry) => entry.isFile() && entry.name.endsWith(".js"))
  .map((entry) => entry.name);

if (javascriptFiles.length === 0) {
  throw new Error(`No production JavaScript assets found in ${assetsDir}`);
}

const forbidden = [
  "/__dev/desk",
  "fixture-calculus",
  "fixture-physics",
  "代入后得到 0/0。0/0 是未定式，不是极限值，所以还需要继续分析并做等价变形。",
];

const violations = [];
for (const filename of javascriptFiles) {
  const source = await readFile(resolve(assetsDir, filename), "utf8");
  for (const marker of forbidden) {
    if (source.includes(marker)) violations.push(`${filename}: ${marker}`);
  }
}

if (violations.length > 0) {
  throw new Error(`Development desk fixtures leaked into the production bundle:\n${violations.join("\n")}`);
}
