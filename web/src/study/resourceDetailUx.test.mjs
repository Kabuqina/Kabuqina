// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("resource packs stay in the study sidebar and open a dedicated route", () => {
  const panel = read("../chat/study/ResourcePackPanel.tsx");
  const main = read("../main.tsx");

  assert.match(panel, /cmdStudyDrafts\("resource_pack"\)/);
  assert.match(panel, /nav\(`\/study\/resources\/\$\{encodeURIComponent\(draft\.artifact_id\)\}`\)/);
  assert.match(main, /path="\/study\/resources\/:artifactId"/);
});

test("the full-page renderer supports article markdown, code, and images", () => {
  const page = read("./ResourceDetailPage.tsx");
  const renderer = read("../chat/study/ResourceRenderer.tsx");
  const markdown = read("../chat/ChatMarkdown.tsx");

  assert.match(page, /cmdStudyArtifactDetail\(artifactId\)/);
  assert.match(page, /max-w-6xl/);
  assert.match(renderer, /variant="article"/);
  assert.match(renderer, /ResourceImages/);
  assert.match(markdown, /variant\?: "chat" \| "article"/);
  assert.match(markdown, /article \? "p-5/);
});
