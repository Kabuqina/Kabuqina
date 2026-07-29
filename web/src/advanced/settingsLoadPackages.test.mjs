/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const settingsSource = fs.readFileSync(new URL("./Settings.tsx", import.meta.url), "utf8");
const loadPackagesSource = fs.readFileSync(
  new URL("./settings/SettingsLoadPackages.tsx", import.meta.url),
  "utf8",
);
const loadPackageUiSource = fs.readFileSync(new URL("./settings/loadPackageUi.ts", import.meta.url), "utf8");
const chatApiSource = fs.readFileSync(new URL("../chat/chat-api.ts", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");
const mainSource = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");
const loadPackagesPageSource = fs.readFileSync(
  new URL("./pages/LoadPackagesPage.tsx", import.meta.url),
  "utf8",
);
const approvalDialogSource = fs.readFileSync(new URL("../components/ApprovalDialogHost.tsx", import.meta.url), "utf8");
const chatMessageListSource = fs.readFileSync(new URL("../chat/ChatMessageList.tsx", import.meta.url), "utf8");
const loadPackageDownloadsSource = fs.readFileSync(
  new URL("../chat/hooks/useLoadPackageDownloads.ts", import.meta.url),
  "utf8",
);
const chatPageSource = fs.readFileSync(new URL("../chat/ChatPage.tsx", import.meta.url), "utf8");

assert.match(
  settingsSource,
  /SettingsLoadPackages/,
  "Settings should mount the generic load-package manager.",
);
assert.doesNotMatch(
  settingsSource,
  /SettingsFormulaModel/,
  "Settings should not mount the old formula-only model block.",
);
assert.match(
  loadPackagesSource,
  /settings\.loadPackagesOpen/,
  "Settings should show a compact entry point for the dedicated load-package page.",
);
assert.match(
  mainSource,
  /\/settings\/load-packages[\s\S]*LoadPackagesPage/,
  "The app router should expose a dedicated load-package settings page.",
);
assert.match(
  loadPackagesPageSource,
  /cmdLoadPackages[\s\S]*packages\.map[\s\S]*job/,
  "The dedicated load-package page should render packages and job progress returned by the generic API.",
);
assert.match(
  loadPackagesPageSource,
  /job\.status !== "running" && job\.status !== "error"/,
  "The dedicated load-package page should hide stale 100% progress bars after a package is installed.",
);
assert.match(
  chatApiSource,
  /usedByCapabilities\?: Array<\{ id: string; title: string \}>/,
  "The web load-package type should expose product capabilities that use each package.",
);
assert.match(
  chatApiSource,
  /realPath\?: string[\s\S]*agentPath\?: string[\s\S]*workspaceIndexPath\?: string[\s\S]*source\?: string/,
  "The web load-package type should expose real, agent-visible, workspace index, and source path metadata.",
);
assert.match(
  loadPackagesPageSource,
  /usedByCapabilities[\s\S]*settings\.loadPackageUsedBy/,
  "The load-package page should show which product capabilities use each package.",
);
assert.doesNotMatch(
  loadPackagesPageSource,
  /settings\.loadPackageRealPath|settings\.loadPackageAgentPath|settings\.loadPackageWorkspaceIndexPath/,
  "The dedicated load-package page should NOT expose raw filesystem paths to users.",
);
assert.match(
  chatMessageListSource,
  /loadPackageDownloads[\s\S]*LoadPackageDownloadProgress/,
  "The chat transcript should surface active load-package downloads.",
);
assert.match(
  loadPackageDownloadsSource,
  /LOAD_PACKAGE_IDLE_POLL_MS[\s\S]*setInterval[\s\S]*LOAD_PACKAGE_IDLE_POLL_MS/,
  "The chat load-package hook should keep a slow idle poll so downloads started after chat mount are discovered.",
);
assert.match(
  loadPackageDownloadsSource,
  /LOAD_PACKAGE_ACTIVE_POLL_MS[\s\S]*downloads\.some\(\(pkg\) => pkg\.job\?\.status === "running"\)/,
  "The chat load-package hook should switch to a fast poll while any package is downloading.",
);
assert.match(
  chatMessageListSource,
  /loadPackageFinished[\s\S]*settings\.loadPackageChatOpenSettings/,
  "The chat transcript should briefly show completed or failed load-package downloads with a settings detail action.",
);
assert.match(
  chatApiSource,
  /cmd_load_packages[\s\S]*cmd_load_package_download[\s\S]*cmd_load_package_delete/,
  "The web API should use the generic Tauri load-package commands.",
);
assert.match(
  chatApiSource,
  /desktop_bridge_unavailable/,
  "The load-package API should throw a stable error when the Tauri bridge is unavailable.",
);
assert.match(
  chatApiSource,
  /__TAURI_INTERNALS__[\s\S]*invoke/,
  "The load-package API should check for the actual Tauri invoke bridge.",
);
assert.match(
  loadPackageUiSource,
  /loadPackagesDesktopOnly/,
  "The Settings UI should show a friendly desktop-only message instead of raw invoke errors.",
);
assert.doesNotMatch(
  chatApiSource,
  /cmd_formula_model_|FormulaModelStatus|cmdFormulaModel/,
  "The web API should not expose the old formula-only commands.",
);
assert.match(settingsSource, /role="tablist"/, "Settings should use a tab bar to group its sections.");
assert.match(
  settingsSource,
  /settings\.tabGeneral[\s\S]*settings\.tabStudy[\s\S]*settings\.tabModel[\s\S]*settings\.tabAdvanced/,
  "Settings should group its sections into category tabs instead of one long scroll.",
);
assert.doesNotMatch(
  settingsSource,
  /settings\.tabGateway|SettingsGateway|useGatewayStatus/,
  "The mobile Bot settings tab was removed (CTL-C08) and must not come back.",
);
assert.doesNotMatch(
  settingsSource,
  /scrollTop|scrollBottom|ArrowUp|ArrowDown/,
  "The tabbed Settings layout should drop the floating scroll-to-top/bottom buttons.",
);
assert.match(stringsSource, /tabGeneral:\s*"常规"/);
assert.match(stringsSource, /tabStudy:\s*"学习"/);
assert.match(
  settingsSource,
  /tab === "study"[\s\S]*SettingsImportReadMode[\s\S]*SettingsReviewLimits[\s\S]*SettingsMaterialPrivacy[\s\S]*SettingsStudyImprovementCounts[\s\S]*SettingsLearningData[\s\S]*SettingsLearningMigrations/,
  "Study preferences, privacy, local data, and diagnostics should live together in the Study tab.",
);

assert.match(stringsSource, /loadPackagesTitle/);
assert.match(stringsSource, /loadPackagesDesktopOnly/);
assert.match(stringsSource, /loadPackagesOpen/);
assert.match(stringsSource, /loadPackageProgress/);
assert.match(stringsSource, /loadPackageUsedBy/);
assert.match(stringsSource, /modelDownloadTitle:\s*"需要下载 \{\{name\}\}"/);
assert.match(stringsSource, /modelSize:\s*"大小"/);
assert.match(
  approvalDialogSource,
  /packageTitle[\s\S]*modelDownloadTitle/,
  "The optional-model approval dialog should title downloads with the concrete package name.",
);

assert.match(stringsSource, /docling-codeformula/);
assert.match(stringsSource, /docling-base/);
assert.match(stringsSource, /local-stt-base-q5_1/);

assert.doesNotMatch(
  chatPageSource,
  /cmdLoadPackageDownload/,
  "Chat/onboarding must not trigger load-package downloads — the desk server self-heals them serially at boot.",
);
assert.doesNotMatch(
  chatPageSource,
  /docling-base/,
  "Load-package auto-download logic must not live in the chat page.",
);
assert.match(
  loadPackageDownloadsSource,
  /cmdLoadPackages/,
  "The chat still polls load-package status to show download progress.",
);
