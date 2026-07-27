// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { KabuqinaSceneSvg } from "./KabuqinaSceneSvg";
import { GENERATED_SCENE_FILENAMES } from "../../lib/artAssets";

const brandDir = path.dirname(fileURLToPath(import.meta.url));
const publicDir = path.resolve(brandDir, "../../../public");

const heroTitle = "Kabuqina chat hero — cup on gingham coaster";
const pillTitle = "Kabuqina companion pill";

const heroMarkup = renderToStaticMarkup(
  createElement(KabuqinaSceneSvg, {
    variant: "hero",
    embedded: true,
    decorative: false,
    title: heroTitle,
    "aria-label": heroTitle,
  }),
);

const pillMarkup = renderToStaticMarkup(
  createElement(KabuqinaSceneSvg, {
    variant: "pill",
    embedded: true,
    decorative: false,
    title: pillTitle,
    "aria-label": pillTitle,
  }),
);

function formatSvgMarkup(markup: string): string {
  return markup
    .replace(/></g, ">\n<")
    .replace(/(<\/(?:svg|defs|g)>)/g, "$1\n")
    .replace(/\n{3,}/g, "\n\n");
}

const heroSvg = `<?xml version="1.0" encoding="UTF-8"?>\n${formatSvgMarkup(heroMarkup)}\n`;
const pillSvg = `<?xml version="1.0" encoding="UTF-8"?>\n${formatSvgMarkup(pillMarkup)}\n`;
const heroPath = path.join(publicDir, GENERATED_SCENE_FILENAMES.chatHero);
const pillPath = path.join(publicDir, GENERATED_SCENE_FILENAMES.companionPill);

writeFileSync(heroPath, heroSvg, "utf8");
writeFileSync(pillPath, pillSvg, "utf8");
console.log(`Wrote ${heroPath}`);
console.log(`Wrote ${pillPath}`);
