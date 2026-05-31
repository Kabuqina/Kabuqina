/* global URL, process */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import ts from "typescript";

async function importTs(relativePath) {
  const sourcePath = new URL(relativePath, import.meta.url);
  const source = fs.readFileSync(sourcePath, "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      verbatimModuleSyntax: true,
    },
  }).outputText;
  const tempPath = path.join(
    os.tmpdir(),
    `kabuqina-chat-ux-${path.basename(relativePath, ".ts")}-${process.pid}-${Date.now()}.mjs`,
  );
  fs.writeFileSync(tempPath, compiled, "utf8");
  try {
    return await import(pathToFileURL(tempPath).href);
  } finally {
    fs.rmSync(tempPath, { force: true });
  }
}

const { deriveSessionPresentation } = await importTs("./sessionPresentation.ts");
const { friendlyChatError } = await importTs("./friendlyError.ts");
const { parseDeskUserContent, DESK_UI_PERSIST_PREFIX } = await importTs("./deskUserContent.ts");
const useChatStateSource = fs.readFileSync(new URL("./hooks/useChatState.ts", import.meta.url), "utf8");
const sidebarSource = fs.readFileSync(new URL("./ChatSidebar.tsx", import.meta.url), "utf8");
const messageListSource = fs.readFileSync(new URL("./ChatMessageList.tsx", import.meta.url), "utf8");
const chatMessageSource = fs.readFileSync(new URL("./ChatMessage.tsx", import.meta.url), "utf8");

const now = new Date("2026-05-13T10:00:00+08:00");

assert.deepEqual(
  deriveSessionPresentation(
    {
      id: "reminder-1",
      title: "1 分钟后提醒我喝水",
      preview: "请提醒我喝水",
      last_active: Math.floor(now.getTime() / 1000),
    },
    "zh",
    now,
  ),
  {
    label: "喝水提醒",
    group: "今天",
    kind: "reminder",
    icon: "alarm",
  },
);

assert.deepEqual(
  deriveSessionPresentation(
    {
      id: "hermesdesk-reminders",
      title: "定时任务记录",
      preview: "⏰ 喝水",
      last_active: Math.floor(now.getTime() / 1000),
    },
    "zh",
    now,
  ),
  {
    label: "小娜提醒",
    group: "今天",
    kind: "reminder",
    icon: "alarm",
  },
);

assert.deepEqual(
  deriveSessionPresentation(
    {
      id: "intro-1",
      title: "你是谁？",
      preview: "你是谁？",
      last_active: Math.floor(now.getTime() / 1000) - 3 * 86400,
    },
    "zh",
    now,
  ),
  {
    label: "小娜的自我介绍",
    group: "最近",
    kind: "chat",
    icon: "message",
  },
);

assert.deepEqual(
  deriveSessionPresentation(
    {
      id: "file-1",
      title: "D:\\Downloads\\report.pdf",
      preview: "帮我看看这个文件 D:\\Downloads\\report.pdf",
      last_active: Math.floor(now.getTime() / 1000),
    },
    "en",
    now,
  ),
  {
    label: "File help",
    group: "Today",
    kind: "file",
    icon: "file",
  },
);

assert.equal(
  friendlyChatError("permission denied while opening file", "zh"),
  "我现在没有权限处理这个文件。你可以先把文件拖进来，或换一个我能访问的位置。",
);

assert.equal(
  friendlyChatError("Stream failed", "en"),
  "I lost the reply halfway through. Please try again, and I can pick it back up.",
);

assert.equal(
  friendlyChatError("Tool execution failed.", "zh"),
  "这个步骤我没成功。你可以换个说法，或把要处理的文件拖进来再试。",
);

assert.equal(
  friendlyChatError('{"error":"run_failed","detail":"terminal can read json files"}', "zh"),
  "这个步骤我没成功。你可以换个说法，或把要处理的文件拖进来再试。",
  "Generic JSON-shaped errors should not map to the bundle/json copy.",
);

assert.equal(
  friendlyChatError("JSONDecodeError: Expecting value", "zh"),
  "本机助手返回的内容我没读懂。请重启应用，或重新构建 Python bundle 后再试。",
);

assert.doesNotMatch(
  sidebarSource,
  /data-action-priority="low"[\s\S]*t\("chat\.exportButton"\)|nav\("\/export"\)/,
  "Export chat should move out of the left rail.",
);

assert.match(
  sidebarSource,
  /collapsed\?: boolean/,
  "ChatSidebar should accept a collapsed prop.",
);

assert.match(
  sidebarSource,
  /onToggleCollapsed/,
  "ChatSidebar should expose a left-rail collapse action.",
);

assert.doesNotMatch(
  sidebarSource,
  /nav\("\/capabilities"\)|t\("capabilities\.title"\)/,
  "Capability should not be duplicated in the left rail.",
);

assert.match(
  sidebarSource,
  /onNewChat[\s\S]*onToggleCollapsed/,
  "The left-rail collapse button should sit after New Chat in the header.",
);

assert.doesNotMatch(
  messageListSource,
  /整理文件[\s\S]*帮我整理桌面文件/,
  "Desktop organizing should not regress to a prompt-only shortcut.",
);

const assistantAvatarSource = fs.readFileSync(
  new URL("../components/AssistantAvatar.tsx", import.meta.url),
  "utf8",
);
assert.match(
  chatMessageSource,
  /<AssistantAvatar/,
  "Assistant messages should render the mascot avatar beside the bubble.",
);
assert.match(assistantAvatarSource, /kabuqina_mascot\.svg[\s\S]*kq-assistant-avatar/);

assert.doesNotMatch(
  chatMessageSource,
  /kq-user-avatar|<User\b|user avatar/i,
  "User messages should stay as clean bubbles without a user avatar.",
);

const chatPageSource = fs.readFileSync(new URL("./ChatPage.tsx", import.meta.url), "utf8");
const chatApiSource = fs.readFileSync(new URL("./chat-api.ts", import.meta.url), "utf8");
const sendMessageSource = fs.readFileSync(new URL("./hooks/useSendMessage.ts", import.meta.url), "utf8");
const desktopApiSource = fs.readFileSync(new URL("./desktop-organizer-api.ts", import.meta.url), "utf8");
const workbenchLayoutSource = fs.readFileSync(
  new URL("./hooks/useWorkbenchLayout.ts", import.meta.url),
  "utf8",
);
const workspacePanelSource = fs.readFileSync(
  new URL("./WorkspacePanel.tsx", import.meta.url),
  "utf8",
);
const chatInputSource = fs.readFileSync(new URL("./ChatInput.tsx", import.meta.url), "utf8");
const appScaffoldSource = fs.readFileSync(new URL("../components/AppScaffold.tsx", import.meta.url), "utf8");
const titleBarSource = fs.readFileSync(new URL("../components/WindowTitleBar.tsx", import.meta.url), "utf8");
const indexCssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");

assert.match(indexCssSource, /kq-assistant-avatar-image[\s\S]*object-fit:\s*contain/);
assert.match(indexCssSource, /kq-assistant-avatar-image[\s\S]*drop-shadow/);

assert.match(
  chatPageSource,
  /handleOrganizeDesktop[\s\S]*role: "user"[\s\S]*desktopOrganizer\.userAction[\s\S]*role: "assistant"/,
  "One-click desktop organizing should add a visible user action and assistant result to chat.",
);

assert.match(
  chatPageSource,
  /useWorkbenchLayout/,
  "ChatPage should use the workbench layout hook.",
);

assert.match(
  chatPageSource,
  /WorkspacePanel/,
  "ChatPage should render the workspace panel.",
);

assert.match(
  chatPageSource,
  /buildWorkspaceState[\s\S]*messages[\s\S]*pendingAttachments[\s\S]*progress/,
  "ChatPage should derive workspace state from messages, attachments, and agent progress.",
);

assert.match(
  chatPageSource,
  /materials=\{workspace\.materials\}[\s\S]*outputs=\{workspace\.outputs\}[\s\S]*activeTool=\{workspace\.activeTool\}/,
  "ChatPage should pass live workspace materials, outputs, and active work into WorkspacePanel.",
);

assert.match(
  chatPageSource,
  /toggleFocusMode/,
  "ChatPage should expose focus mode controls.",
);

assert.match(
  chatPageSource,
  /PanelLeftOpen/,
  "The left-rail expand button should remain available in the center header.",
);

assert.doesNotMatch(
  chatPageSource,
  /chat\.activeWork/,
  "The center header should not render the redundant active-work label.",
);

assert.doesNotMatch(
  chatPageSource,
  /DesktopOrganizerModal|desktopOrganizerOpen|setDesktopOrganizerOpen/,
  "One-click desktop organizing should not open a modal confirmation flow.",
);

assert.match(
  desktopApiSource,
  /cmd_desktop_organize_run/,
  "Desktop organizing should call the one-click Tauri command.",
);

assert.match(
  workbenchLayoutSource,
  /WORKBENCH_LAYOUT_KEY\s*=\s*"kabuqina\.workbench\.layout"/,
  "Workbench layout should persist under a Kabuqina-specific localStorage key.",
);

assert.match(
  workbenchLayoutSource,
  /toggleFocusMode/,
  "Workbench layout hook should expose a focus mode toggle.",
);

assert.match(
  workbenchLayoutSource,
  /isNarrow/,
  "Workbench layout hook should track narrow-window behavior.",
);

assert.match(
  workspacePanelSource,
  /workspace\.currentGoal/,
  "Workspace panel should render a Current Goal section.",
);

assert.match(
  workspacePanelSource,
  /workspace\.materials/,
  "Workspace panel should render a Materials section.",
);

assert.match(
  workspacePanelSource,
  /workspace\.outputs/,
  "Workspace panel should render an Outputs section.",
);

assert.match(
  workspacePanelSource,
  /materials\.length[\s\S]*items=\{materials\}/,
  "Workspace panel should render dynamic materials.",
);

assert.match(
  workspacePanelSource,
  /outputs\.length[\s\S]*items=\{outputs\}/,
  "Workspace panel should render dynamic outputs.",
);

assert.match(
  workspacePanelSource,
  /activeTool[\s\S]*activity\.map/,
  "Workspace panel should render current work and recent activity.",
);

assert.match(
  workspacePanelSource,
  /workspace\.quickActions/,
  "Workspace panel should render a Quick Actions section.",
);

assert.match(
  indexCssSource,
  /--kq-color-ink:\s*#5A4A6A[\s\S]*--kq-color-primary:\s*#B8A9C9[\s\S]*--kq-shadow-soft/,
  "Kabuqina chat styling should expose the lavender-pink visual tokens.",
);

assert.match(
  indexCssSource,
  /\[data-theme="dark"\][\s\S]*--kq-color-ink:\s*#e2dde8/,
  "Dark theme should override Kabuqina semantic tokens via data-theme.",
);

assert.match(
  appScaffoldSource,
  /kq-chat-shell/,
  "The chat scaffold should use the Kabuqina soft lavender shell.",
);

assert.match(
  titleBarSource,
  /grid-cols-\[1fr_auto_1fr\][\s\S]*kq-titlebar-nav[\s\S]*justify-center[\s\S]*kq-titlebar-controls[\s\S]*justify-end/,
  "The title bar should keep the main navigation centered while window controls stay on the right.",
);

assert.match(
  titleBarSource,
  /kq-titlebar/,
  "The title bar should use the Kabuqina lavender system instead of the default blue/zinc treatment.",
);

for (const className of ["kq-titlebar-brand", "kq-titlebar-link", "kq-titlebar-link-active", "kq-titlebar-control"]) {
  assert.match(titleBarSource, new RegExp(className), `Title bar should include ${className}.`);
}

assert.match(
  messageListSource,
  /productName[\s\S]*kq-empty-title[\s\S]*\u6162\u6162\u6765\uff0c\u5c0f\u5a1c\u966a\u4f60\u6574\u7406\u601d\u8def[\s\S]*kabuqina_hero_scene\.svg[\s\S]*kq-companion-hero-scene/,
  "The empty chat state should show Kabuqina and render the exported hero scene SVG.",
);

assert.match(
  sidebarSource,
  /kq-sidebar[\s\S]*kq-new-chat/,
  "The chat sidebar should use the Kabuqina frosted sidebar and lavender new-chat button.",
);

assert.match(
  chatInputSource,
  /kq-input-area[\s\S]*kq-input-container[\s\S]*kq-composer[\s\S]*kq-send-button/,
  "The chat composer should use the reference-style centered bottom input layout.",
);

assert.match(
  chatInputSource,
  /kq-input-footer[\s\S]*justify-center[\s\S]*chat\.hint/,
  "The input hint should stay centered below the composer.",
);

assert.doesNotMatch(
  chatInputSource,
  /settings\.powerTitle|kq-power-toggle/,
  "Power-user toggle should not live in the chat input footer.",
);

const togglePowerSource = fs.readFileSync(new URL("../lib/useTogglePowerUser.ts", import.meta.url), "utf8");
assert.match(togglePowerSource, /confirm\([\s\S]*tone:\s*"warning"/);
assert.doesNotMatch(togglePowerSource, /plugin-dialog/);
assert.match(titleBarSource, /useTogglePowerUser/);
assert.match(
  fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8"),
  /ConfirmDialogHost/,
  "App shell should mount the in-app confirm dialog host.",
);
assert.match(
  chatPageSource,
  /handleDelete[\s\S]*confirm\([\s\S]*chat\.deleteTitle[\s\S]*tone:\s*"danger"/,
  "Session delete should use the in-app confirm dialog.",
);
assert.doesNotMatch(chatPageSource, /window\.confirm/);
assert.match(
  titleBarSource,
  /kq-titlebar-power[\s\S]*settings\.powerTitle[\s\S]*togglePowerUser/,
  "Power-user toggle should sit in the titlebar beside capabilities.",
);

assert.match(messageListSource, /kq-empty-action-icon/);
assert.match(messageListSource, /strokeWidth=\{2\.25\}/);
assert.match(
  messageListSource,
  /kq-color-icon-book[\s\S]*kq-color-icon-folder[\s\S]*kq-color-icon-alarm[\s\S]*kq-color-icon-pen/,
  "Empty-state quick actions should use unified colorful icon strokes.",
);

assert.match(
  messageListSource,
  /grid-cols-\[repeat\(auto-fit,minmax\(10\.5rem,1fr\)\)\]/,
  "Empty-state quick actions should wrap on narrow screens.",
);

assert.match(
  chatMessageSource,
  /kq-chat-bubble-user[\s\S]*kq-chat-bubble-assistant/,
  "Chat message bubbles should use the Kabuqina user and assistant bubble treatments.",
);

assert.match(
  chatApiSource,
  /export type UiMsg[\s\S]*attachments\?: DeskAttachmentPayload\[\]/,
  "Chat UI messages should preserve attachment payloads for front-end previews.",
);

assert.match(
  sendMessageSource,
  /const imageAtts[\s\S]*mime\.startsWith\("image\/"\)[\s\S]*const fileAttLabel[\s\S]*attachments: atts/,
  "Sending a message should keep image attachments on the UI message instead of only rendering a file-name line.",
);

assert.match(
  chatApiSource,
  /AgentInteractionRequest[\s\S]*cmdInteractionResponse/,
  "Chat API should expose reusable agent interaction request/response types.",
);

assert.match(
  sendMessageSource,
  /interaction\.request[\s\S]*setPendingInteraction/,
  "Streaming chat should capture agent interaction requests for the UI.",
);

assert.match(
  sendMessageSource,
  /deferredStreamError[\s\S]*chat stream error \(deferred\)/,
  "Stream error SSE events should be deferred until the stream command finishes.",
);

assert.match(
  sendMessageSource,
  /parsed\.ok[\s\S]*setSendErr\(null\)/,
  "Successful stream completion should clear any stale sendErr banner.",
);

assert.match(
  messageListSource,
  /AgentInteractionCard[\s\S]*通过[\s\S]*补充要求[\s\S]*自行编辑/s,
  "Chat should render reusable interaction cards with the PPT outline review actions.",
);

assert.match(
  chatMessageSource,
  /attachments\?: DeskAttachmentPayload\[\][\s\S]*UserImageAttachments[\s\S]*<img[\s\S]*data:\$\{att\.mime\};base64,\$\{att\.data\}/,
  "User bubbles should render image attachments as visible screenshots.",
);

assert.match(
  messageListSource,
  /attachments=\{m\.attachments\}/,
  "ChatMessageList should pass message attachments into each rendered bubble.",
);

assert.equal(
  parseDeskUserContent(`${DESK_UI_PERSIST_PREFIX}{"text":"hi","attachments":[{"name":"shot.png","mime":"image/png","data":"abc"}]}`).text,
  "hi",
  "Desk UI persist envelope should restore user text.",
);
assert.equal(
  parseDeskUserContent(`${DESK_UI_PERSIST_PREFIX}{"text":"","attachments":[{"name":"shot.png","mime":"image/png","data":"abc"}]}`).attachments?.[0]?.name,
  "shot.png",
  "Desk UI persist envelope should restore image attachments for history replay.",
);
assert.equal(
  parseDeskUserContent("[1 image(s)]").text,
  "（1 张图片，历史记录中无法预览）",
  "Legacy image-only placeholders should not render raw [N image(s)] text.",
);

assert.match(
  useChatStateSource,
  /parseDeskUserContent[\s\S]*attachments/,
  "Loading session history should map desk UI persist envelopes into UiMsg attachments.",
);

assert.match(
  chatPageSource,
  /message\.attachments[\s\S]*att\.mime/,
  "Workspace state should also recognize image attachments stored on user messages.",
);

assert.match(
  workspacePanelSource,
  /kq-workspace-panel/,
  "Workspace panel should use the Kabuqina frosted panel treatment.",
);

assert.match(
  workspacePanelSource,
  /kq-workspace-card/,
  "Workspace sections should render as lavender-tinted cards.",
);

assert.match(
  indexCssSource,
  /\.kq-section-heading[\s\S]*border-left:\s*3px[\s\S]*background:\s*rgba\(243,\s*237,\s*246/,
  "Workspace section headings should use a subtle left accent instead of heavy lavender pills.",
);

assert.match(
  workspacePanelSource,
  /nav\("\/export"\)[\s\S]*chat\.exportButton/,
  "Workspace quick actions should include Export Chat.",
);

const exportPageSource = fs.readFileSync(new URL("../advanced/Export.tsx", import.meta.url), "utf8");
const chatExportSource = fs.readFileSync(new URL("./chatExport.ts", import.meta.url), "utf8");
assert.match(
  exportPageSource,
  /buildExportJson[\s\S]*buildExportMarkdown[\s\S]*exportLabelsForLocale/,
  "Export page should build branded dialogue exports via chatExport helpers.",
);
assert.match(chatExportSource, /parseDeskUserContent[\s\S]*speaker: labels\.productName/);
assert.doesNotMatch(chatExportSource, /Hermes|hermesdesk-export/i);

assert.match(
  workspacePanelSource,
  /nav\("\/settings\/cron"[\s\S]*kq-color-icon-alarm[\s\S]*cron\.title[\s\S]*kq-color-icon-folder[\s\S]*workspaceOrganizeDesktop[\s\S]*kq-color-icon-download[\s\S]*chat\.exportButton/,
  "Workspace quick actions should use colorful icons with scheduled tasks first.",
);

assert.match(
  workspacePanelSource,
  /workspaceCourseToPpt[\s\S]*course_report[\s\S]*workspacePaperToPpt[\s\S]*workspaceCodeToPpt[\s\S]*workspacePrecisePdf[\s\S]*review_outline[\s\S]*pptx_write[\s\S]*pdf_read_precise|review_outline[\s\S]*pptx_write[\s\S]*pdf_read_precise[\s\S]*workspaceCourseToPpt[\s\S]*workspacePaperToPpt[\s\S]*workspaceCodeToPpt[\s\S]*workspacePrecisePdf/,
  "Workspace quick actions should expose student PPT and precise PDF workflows.",
);

assert.match(
  workspacePanelSource,
  /高质量可交付[\s\S]*slide_type[\s\S]*screenshot_placeholder[\s\S]*chart_placeholder[\s\S]*qa_backup[\s\S]*review_outline[\s\S]*pptx_write/,
  "Student PPT quick actions should request structured high-quality deliverables with placeholders and backup slides.",
);

assert.match(
  workspacePanelSource,
  /material_index_build[\s\S]*素材索引[\s\S]*review_outline[\s\S]*pptx_write/,
  "Student PPT quick actions should build a general material index before outline review and PPT writing.",
);

assert.doesNotMatch(
  workspacePanelSource,
  /workspaceAddFile|workspaceCapture|FilePlus2|Camera/,
  "Workspace quick actions should not show unfinished Add File or Screenshot actions.",
);

assert.match(
  sidebarSource,
  /kq-sidebar-group-divided[\s\S]*kq-sidebar-group-label[\s\S]*kq-sidebar-session-label/,
  "Sidebar history groups should use dividers and stronger group labels.",
);

assert.match(
  sidebarSource,
  /REMINDER_SESSION_ID[\s\S]*kq-color-icon-alarm/,
  "Only the fixed Nana reminder log session should use the colorful alarm icon.",
);

assert.doesNotMatch(
  sidebarSource,
  /kq-reminder-card|cron\.title/,
  "Scheduled tasks entry should not live in the sidebar footer.",
);

assert.match(
  indexCssSource,
  /kq-titlebar[\s\S]*kq-titlebar-link-active/,
  "The chat CSS should define unified titlebar, readable workspace headings, and lavender footer toggle styling.",
);

assert.match(
  titleBarSource,
  /kq-titlebar-nav[\s\S]*kq-titlebar-companion-btn[\s\S]*kq-titlebar-sparkle-grad/,
  "Shrink-to-pill sparkle should sit in the centered titlebar nav with a colorful gradient.",
);
assert.match(titleBarSource, /onShowCompanion[\s\S]*cmd_show_companion/);
assert.match(indexCssSource, /kq-titlebar-companion-btn/);
assert.match(indexCssSource, /kq-titlebar-power/);
assert.match(indexCssSource, /--radius-shell-lg:\s*0\.75rem/);
assert.match(indexCssSource, /kq-workspace-card[\s\S]*border-radius:\s*var\(--radius-shell-lg\)/);
assert.match(indexCssSource, /hd-glass-subtle[\s\S]*border-radius:\s*var\(--radius-shell-lg\)/);

const {
  getCachedHermesReadiness,
  snapshotFromBootState,
  updateHermesReadinessCache,
} = await importTs("./hermesReadinessCache.ts");
const useHermesReadinessSource = fs.readFileSync(
  new URL("./hooks/useHermesReadiness.ts", import.meta.url),
  "utf8",
);

assert.deepEqual(getCachedHermesReadiness(), {
  hermesReady: false,
  hermesWarming: false,
  bootErr: null,
});

assert.deepEqual(snapshotFromBootState({ port: 12345, warming: false }), {
  hermesReady: true,
  hermesWarming: false,
  bootErr: null,
});

assert.deepEqual(updateHermesReadinessCache({ port: 12345, warming: false }, null), {
  hermesReady: true,
  hermesWarming: false,
  bootErr: null,
});

assert.deepEqual(getCachedHermesReadiness(), {
  hermesReady: true,
  hermesWarming: false,
  bootErr: null,
});

assert.match(
  useHermesReadinessSource,
  /getCachedHermesReadiness[\s\S]*updateHermesReadinessCache/,
  "Chat readiness hook should seed UI from a route-surviving cache.",
);

const reminderSessionSource = fs.readFileSync(new URL("./reminderSession.ts", import.meta.url), "utf8");
const chatPageReminderSource = fs.readFileSync(new URL("./ChatPage.tsx", import.meta.url), "utf8");
assert.match(reminderSessionSource, /hermesdesk-reminders/);
assert.match(chatPageReminderSource, /openReminderSession[\s\S]*REMINDER_SESSION_ID/);
assert.match(workspacePanelSource, /\/settings\/cron/);
