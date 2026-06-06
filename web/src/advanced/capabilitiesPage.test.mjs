/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const pageSource = fs.readFileSync(new URL("./pages/CapabilitiesPage.tsx", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");

assert.match(
  pageSource,
  /type ProductCapabilityItem[\s\S]*requiredLoadPackages[\s\S]*optionalLoadPackages/,
  "Capabilities page should type the backend product capabilities payload, including load packages.",
);
assert.match(
  pageSource,
  /type CapabilityCatalog[\s\S]*capabilities: ProductCapabilityItem\[\]/,
  "Capabilities catalog should read catalog.capabilities from the backend payload.",
);
assert.match(
  pageSource,
  /invoke<unknown>\("cmd_capabilities_catalog"\)[\s\S]*normalizeCapabilityCatalog\(result\)/,
  "Capabilities catalog should normalize backend payloads before storing them in React state.",
);
assert.match(
  pageSource,
  /function normalizeCapabilityCatalog[\s\S]*capabilities: asArray\(record\.capabilities\)[\s\S]*skills: asArray\(record\.skills\)[\s\S]*toolsets: asArray\(record\.toolsets\)[\s\S]*plugins: asArray\(record\.plugins\)[\s\S]*function asArray[\s\S]*Array\.isArray/,
  "Capabilities catalog normalization should tolerate missing list fields from older runtimes.",
);
assert.match(
  pageSource,
  /const TABS[\s\S]*id: "product"[\s\S]*id: "skills"[\s\S]*id: "tools"[\s\S]*id: "plugins"/,
  "Product capabilities should be the first top-level tab.",
);
assert.match(
  pageSource,
  /activeTab === "product"[\s\S]*catalog\.capabilities/,
  "The list should render product capabilities from catalog.capabilities.",
);
assert.match(
  pageSource,
  /candidate[\s\S]*available[\s\S]*missing_package[\s\S]*downloading[\s\S]*package_error[\s\S]*disabled_toolset[\s\S]*requires_power_user[\s\S]*unsupported_platform[\s\S]*error/,
  "Product capability rows should cover all backend status badges.",
);
assert.match(
  pageSource,
  /ProductCapabilityDetails[\s\S]*stages[\s\S]*pipelines[\s\S]*shortcuts[\s\S]*requiredToolsets[\s\S]*requiredLoadPackages[\s\S]*optionalLoadPackages[\s\S]*statusReason/,
  "The detail panel should show stages, pipelines, shortcut candidates, product tools, toolsets, load packages, and status reason.",
);
assert.match(
  pageSource,
  /type ProductPipelineStep[\s\S]*defaultArgs[\s\S]*outputs[\s\S]*type ProductPipeline[\s\S]*steps/,
  "Capabilities page should type product capability pipeline steps.",
);
assert.match(
  pageSource,
  /type ProductShortcut[\s\S]*entryPipeline[\s\S]*visibleWhen/,
  "Capabilities page should type shortcut candidate metadata.",
);
assert.match(
  pageSource,
  /cmdLoadPackageDownload[\s\S]*loadPackageError/,
  "Capability details should use the existing load-package download command and friendly error formatter.",
);
assert.doesNotMatch(
  pageSource,
  /cmdLoadPackageDelete/,
  "Capability details should not expose destructive load-package deletion.",
);
assert.match(
  pageSource,
  /ProductCapabilityDetails[\s\S]*onDownload[\s\S]*LoadPackageGroup[\s\S]*onDownload/,
  "Product capability load-package rows should receive a download handler.",
);
assert.match(
  pageSource,
  /const packageBusy = busyLoadPackageId != null \|\| \[\s*\.\.\.item\.requiredLoadPackages,\s*\.\.\.item\.optionalLoadPackages,\s*\]\.some\(\(pkg\) => pkg\.job\?\.status === "running"\)/,
  "Product capability details should disable every load-package button when any required or optional package is already downloading.",
);
assert.match(
  pageSource,
  /\/settings\/load-packages/,
  "Product capability details should link to the full load-package manager.",
);
assert.match(stringsSource, /product: "产品能力"/);
assert.match(stringsSource, /product: "Product capabilities"/);
assert.match(stringsSource, /statusReason/);
assert.match(stringsSource, /candidate: "候选"/);
assert.match(stringsSource, /candidate: "candidate"/);
assert.match(stringsSource, /requires_power_user/);
assert.match(stringsSource, /unsupported_platform/);
assert.match(stringsSource, /requiredLoadPackages/);
assert.match(stringsSource, /optionalLoadPackages/);
assert.match(stringsSource, /pipelineStages/);
assert.match(stringsSource, /pipelineEntrypoints/);
assert.match(stringsSource, /shortcutCandidates/);
