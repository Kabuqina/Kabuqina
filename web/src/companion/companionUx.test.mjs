/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const companionSource = fs.readFileSync(new URL("./CompanionWindow.tsx", import.meta.url), "utf8");
const pillSceneSource = fs.readFileSync(new URL("../components/CompanionPillScene.tsx", import.meta.url), "utf8");
const bootPillSource = fs.readFileSync(new URL("../components/BootPill.tsx", import.meta.url), "utf8");
const splashSource = fs.readFileSync(new URL("../Splash.tsx", import.meta.url), "utf8");
const chatPageSource = fs.readFileSync(new URL("../chat/ChatPage.tsx", import.meta.url), "utf8");
const mainSource = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");
const indexCssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");
const titleBarSource = fs.readFileSync(new URL("../components/WindowTitleBar.tsx", import.meta.url), "utf8");

assert.doesNotMatch(
  companionSource,
  /companion_compact\.png|intrinsicLogicalDimsForAsset|<img/,
  "Compact pill should render the CSS scene, not a PNG mascot.",
);

assert.match(companionSource, /CompanionPillScene/, "Companion window should reuse the shared pill scene.");
assert.match(
  pillSceneSource,
  /kq-companion-pill-mat[\s\S]*CompanionCup[\s\S]*variant="brand"[\s\S]*steam/,
  "Pill scene should render the original CSS mat and brand cup.",
);
assert.doesNotMatch(
  pillSceneSource,
  /KabuqinaSceneSvg/,
  "Pill scene should not use the SVG pill scene.",
);

assert.match(
  companionSource,
  /PILL_REM_W = 6\.2[\s\S]*PILL_REM_H = 6\.15/,
  "Pill window size should track the pill scene (cup + compact mat).",
);

assert.match(
  indexCssSource,
  /kq-companion-pill-float/,
  "Pill scene should use a gentle floating animation.",
);

assert.match(
  companionSource,
  /cmd_resize_companion[\s\S]*cmd_ensure_companion_position/,
  "CompanionWindow should resize then place the pill on the desktop.",
);

assert.match(
  companionSource,
  /onDoubleClick=\{openMain\}/,
  "Double-click compact surface should open the main window.",
);

assert.match(
  companionSource,
  /cmd_focus_main_window/,
  "Opening main should hide the compact pill via focus_main_window.",
);

assert.match(
  companionSource,
  /onCompactPointerMove[\s\S]+getCurrentWindow\(\)\.startDragging/,
  "Compact pointer-move handler should initiate window dragging after threshold.",
);

assert.match(
  mainSource,
  /kq-companion-window/,
  "Companion entry should mark the document root for transparent shell styling.",
);

assert.match(
  companionSource,
  /setShadow\(false\)/,
  "CompanionWindow should disable native window shadow on the pill.",
);

assert.match(
  titleBarSource,
  /cmd_show_companion/,
  "Title bar star should shrink the app into the compact pill.",
);

assert.match(bootPillSource, /kabuqina_boot\.svg/, "Boot pill should show the Kabuqina boot mascot SVG.");
assert.match(bootPillSource, /boot\.starting/, "Boot pill should show a unified starting label.");
assert.match(
  fs.readFileSync(new URL("../components/ApprovalDialogHost.tsx", import.meta.url), "utf8"),
  /hermes-approval-request[\s\S]*cmd_respond_approval/,
  "Approval dialog should listen for bridge events and respond via Tauri command.",
);
assert.match(
  fs.readFileSync(new URL("../components/ApprovalDialogHost.tsx", import.meta.url), "utf8"),
  /model_download[\s\S]*modelDownloadTitle/,
  "Approval dialog should handle optional model download confirmations.",
);
assert.match(splashSource, /BootPill/, "Splash should use the boot pill instead of staged splash copy.");
assert.match(splashSource, /waitForHermesReadiness/, "Splash should wait for Hermes before entering chat.");
assert.match(
  chatPageSource,
  /BootPill/,
  "Chat should use the boot pill for warm-up instead of separate waiting strings.",
);
assert.doesNotMatch(
  chatPageSource,
  /chat\.waitingHermesWarm/,
  "Chat warm-up should not expose a second waiting message.",
);
