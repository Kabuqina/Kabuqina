import assert from "node:assert/strict";
import fs from "node:fs";

const cupSource = fs.readFileSync(new URL("./CompanionCupSvg.tsx", import.meta.url), "utf8");
const coasterSource = fs.readFileSync(new URL("./KabuqinaCoasterSvg.tsx", import.meta.url), "utf8");
const tokenSource = fs.readFileSync(new URL("./kabuqinaBrandTokens.ts", import.meta.url), "utf8");

assert.match(
  cupSource,
  /M 70 41\.32 C 99 43\.2 99 66\.8 70 69\.2/,
  "Cup handle should extend farther right than the original CSS geometry.",
);

assert.match(tokenSource, /handle: "#9ca3af"/, "Competition cup handle should use the neutral gray palette.");
assert.match(tokenSource, /center: "#d9d9d9"/, "Competition cup fill should use the neutral gray palette.");
assert.match(tokenSource, /line: "#8f75a8"/, "Coaster grid lines should read slightly deeper.");
assert.match(tokenSource, /lineOpacity: 0\.75/, "Coaster grid should read clearly without overpowering.");
assert.match(tokenSource, /borderOpacity: 0\.77/, "Coaster border should separate from the page background.");
assert.match(tokenSource, /contactOpacity: 0\.38/, "Cup/coaster contact shadow should be more legible.");

assert.doesNotMatch(coasterSource, /fill=\{tokens\.coaster\.depth\}/, "Flat coaster should not use a standing depth layer.");
assert.doesNotMatch(coasterSource, /fill=\{tokens\.coaster\.edge\}/, "Coaster should stay light on extra edge layers.");
assert.match(coasterSource, /lineOpacity: 0\.78/, "Pill coaster should read with a bit more contrast.");
assert.match(coasterSource, /gridStrokeWidth: 1\.45/, "Pill coaster grid should stay legible at small sizes.");
assert.match(coasterSource, /zRotate: -6/, "Coaster should keep only a slight tabletop skew.");

assert.match(cupSource, /M 31 17 C 25 9 36 5 30 -3/, "Steam should use curved wisps instead of vertical blobs.");
assert.doesNotMatch(cupSource, /cx="28" cy="8" rx="5\.5" ry="13"/, "Steam should not use the old upright ellipses.");
