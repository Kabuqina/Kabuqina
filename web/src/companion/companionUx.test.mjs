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
  "Compact pill should not regress to the old PNG mascot path.",
);

assert.match(companionSource, /CompanionPillScene/, "Companion window should reuse the shared pill scene.");
assert.match(
  pillSceneSource,
  /kabuqina_pill_scene\.svg[\s\S]*kq-companion-pill-svg/,
  "Pill scene should render the exported SVG pill asset.",
);
assert.doesNotMatch(
  pillSceneSource,
  /CompanionCup|kq-companion-pill-mat|kq-companion-pill-cup/,
  "Pill scene should not rebuild the asset from CSS cup pieces.",
);

assert.match(
  companionSource,
  /PILL_REM_W = 5[\s\S]*PILL_REM_H = 5\.56/,
  "Pill window size should include top headroom for the floating scene.",
);
assert.match(
  companionSource,
  /MENU_REM_W[\s\S]*MENU_REM_H[\s\S]*menuOpen[\s\S]*resizeCompanionWindow/,
  "Right-click replacement menu should temporarily resize the compact window.",
);
assert.match(
  companionSource,
  /menuOpen && "items-end justify-start px-3 pb-2"/,
  "Right-click replacement menu should move the pill away from the menu instead of covering it.",
);
assert.match(
  companionSource,
  /onContextMenu=\{openCompanionMenu\}/,
  "Right-clicking the pill should open the companion replacement menu.",
);
assert.match(
  companionSource,
  /type="file"[\s\S]*accept="image\/png,image\/webp,image\/svg\+xml"/,
  "Companion menu should open a constrained image file picker.",
);
assert.match(
  companionSource,
  /settings\.companionImageSpec/,
  "Companion menu should explain image specs.",
);
assert.doesNotMatch(
  companionSource,
  /kq-companion-context-title/,
  "Companion menu should stay concise and not add a separate title line.",
);
assert.match(
  companionSource,
  /settings\.companionImageReplace/,
  "Companion menu should use replacement wording for the primary action.",
);
assert.match(
  companionSource,
  /validateCustomCompanionImageFile[\s\S]*setCustomCompanionImage/,
  "Companion menu should explain image specs and validate before saving.",
);

assert.match(
  indexCssSource,
  /kq-companion-pill-float/,
  "Pill scene should use a gentle floating animation.",
);
assert.match(
  indexCssSource,
  /kq-companion-context-menu/,
  "Companion right-click menu should have dedicated styling.",
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
assert.match(splashSource, /waitForKabuqinaReadiness/, "Splash should wait for Hermes before entering chat.");
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
