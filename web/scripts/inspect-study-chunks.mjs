// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0
/* global console */

import fs from "node:fs";
import path from "node:path";
import { gzipSync } from "node:zlib";

const dist = path.resolve("dist");
const manifest = JSON.parse(fs.readFileSync(path.join(dist, ".vite", "manifest.json"), "utf8"));

function dependencyKeys(rootKey, includeDynamic = false) {
  const seen = new Set();
  const visit = (key) => {
    if (seen.has(key)) return;
    seen.add(key);
    const item = manifest[key];
    for (const imported of item?.imports ?? []) visit(imported);
    if (includeDynamic) for (const imported of item?.dynamicImports ?? []) visit(imported);
  };
  visit(rootKey);
  return seen;
}

function filesFor(keys) {
  const files = new Set();
  for (const key of keys) {
    const item = manifest[key];
    if (!item) continue;
    if (item.file) files.add(item.file);
    for (const css of item.css ?? []) files.add(css);
  }
  return [...files];
}

function measure(files) {
  let raw = 0;
  let gzip = 0;
  for (const file of files) {
    const bytes = fs.readFileSync(path.join(dist, file));
    raw += bytes.length;
    gzip += gzipSync(bytes).length;
  }
  return { rawBytes: raw, gzipBytes: gzip, files };
}

const entryKey = Object.keys(manifest).find((key) => manifest[key].isEntry && key === "index.html");
const studyKey = Object.keys(manifest).find((key) => key.endsWith("/study/StudyRoute.tsx"));
if (!entryKey || !studyKey || !manifest[studyKey].isDynamicEntry) {
  throw new Error("Expected index entry and an independent StudyRoute dynamic entry");
}

const initialKeys = dependencyKeys(entryKey, false);
const studyKeys = dependencyKeys(studyKey, false);
const initialSources = [...initialKeys].join("\n").toLowerCase();
const studySources = [...studyKeys].join("\n").toLowerCase();
if (initialSources.includes("/study/studyroute")) throw new Error("StudyRoute leaked into the initial graph");
const studyOwnFile = manifest[studyKey].file;
const studyOwnContent = fs.readFileSync(path.join(dist, studyOwnFile), "utf8").toLowerCase();
for (const forbidden of ["codemirror", "motion", "katex"]) {
  if (studySources.includes(forbidden) || studyOwnContent.includes(forbidden)) {
    throw new Error(`${forbidden} leaked into the StudyRoute graph`);
  }
}

console.log(JSON.stringify({
  entryKey,
  studyKey,
  initial: measure(filesFor(initialKeys)),
  studyOwn: measure([studyOwnFile]),
  study: measure(filesFor(studyKeys)),
}, null, 2));
