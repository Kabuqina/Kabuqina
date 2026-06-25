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
const { isWorkbenchNarrow } = await importTs("./hooks/workbenchLayoutLogic.ts");
const useChatStateSource = fs.readFileSync(new URL("./hooks/useChatState.ts", import.meta.url), "utf8");
const sidebarSource = fs.readFileSync(new URL("./ChatSidebar.tsx", import.meta.url), "utf8");
const messageListSource = fs.readFileSync(new URL("./ChatMessageList.tsx", import.meta.url), "utf8");
const chatMessageSource = fs.readFileSync(new URL("./ChatMessage.tsx", import.meta.url), "utf8");
const agentProgressSource = fs.readFileSync(new URL("./AgentProgress.tsx", import.meta.url), "utf8");

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
// Visual-master palettes were extracted into a shared module so the PptxGenJS
// renderer (renderDeck.ts) and the WorkspacePanel selector use one source.
const visualMastersSource = fs.readFileSync(
  new URL("./pptx/visualMasters.ts", import.meta.url),
  "utf8",
);
const chatInputSource = fs.readFileSync(new URL("./ChatInput.tsx", import.meta.url), "utf8");
const appScaffoldSource = fs.readFileSync(new URL("../components/AppScaffold.tsx", import.meta.url), "utf8");
const titleBarSource = fs.readFileSync(new URL("../components/WindowTitleBar.tsx", import.meta.url), "utf8");
const indexCssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");
const stringsSource = fs.readFileSync(new URL("../locales/strings.ts", import.meta.url), "utf8");

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
  stringsSource,
  /workspaceTitle:\s*"ACADEMY"/,
  "Chat workspace panel title should use ACADEMY.",
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
  sidebarSource,
  /collapsed \? t\("chat\.leftRailExpand"\) : t\("chat\.leftRailCollapse"\)[\s\S]*PanelLeft/,
  "The left-rail toggle should remain available in the sidebar and expose an expand action when collapsed (PanelLeft icon, label flips on collapsed).",
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

assert.equal(
  isWorkbenchNarrow(706),
  false,
  "Windows right-snap width at 125% scaling should still allow expanding workbench sidebars.",
);

assert.equal(
  isWorkbenchNarrow(560),
  true,
  "Very small windows should still collapse workbench sidebars.",
);

assert.match(
  workspacePanelSource,
  /workspace\.reportPpt[\s\S]*workspacePaperToPpt[\s\S]*workspaceCourseToPpt[\s\S]*workspaceCodeToPpt[\s\S]*workspaceSandtableToPpt/,
  "Workspace panel should group the four report PPT workflows under Generate Report PPT, paper first.",
);

assert.match(
  workspacePanelSource,
  /workspace\.mathAbility[\s\S]*workspaceFormulaToCode[\s\S]*workspaceCodeToFormula[\s\S]*workspaceMathFormulaExtract/,
  "Workspace panel should group code/formula conversion and formula extraction under Math Ability, formula-to-code first.",
);
assert.match(
  workspacePanelSource,
  /semantic_contract[\s\S]*定义域\/取值范围[\s\S]*a < c < b[\s\S]*needs_human_check/,
  "Formula-to-code prompt should require semantic contract checks, including open interval constraints.",
);

assert.doesNotMatch(
  workspacePanelSource,
  /workspace\.otherCommon|cron\.title|workspaceOpenWorkspace|workspaceOrganizeDesktop|chat\.exportButton/,
  "Academy panel should not keep non-academy common actions.",
);

assert.match(
  sidebarSource,
  /workspaceOpenWorkspace[\s\S]*cron\.title[\s\S]*workspaceOrganizeDesktop[\s\S]*chat\.exportButton/,
  "Chat sidebar should move non-academy common actions below chat history, open workspace first.",
);

assert.match(
  sidebarSource,
  /kq-sidebar-history-scroll[\s\S]*grouped\.map/,
  "Sidebar chat history should live in its own scroll region.",
);
assert.match(
  sidebarSource,
  /kq-sidebar-history-scroll[\s\S]*<\/div>\s*<div[\s\S]*kq-sidebar-common-actions[\s\S]*workspaceOpenWorkspace/,
  "Sidebar common actions should be outside the scrollable history region so history cannot push them down.",
);

assert.match(
  workspacePanelSource,
  /workspace\.deliverables[\s\S]*DeliverableCard/,
  "Workspace panel should render generated outputs as actionable deliverable cards.",
);
assert.match(
  workspacePanelSource,
  /cmd_open_path[\s\S]*cmd_reveal_path/,
  "Deliverable cards should open and reveal files via the workspace-scoped Tauri commands.",
);
assert.match(
  workspacePanelSource,
  /latestDeliverables/,
  "Deliverables should collapse repeated regenerations to the latest version per filename.",
);
assert.match(
  workspacePanelSource,
  /disabled=\{disabled\}/,
  "Deliverable actions should stay disabled while a turn is still in flight.",
);
assert.match(
  chatPageSource,
  /busy=\{sending\}/,
  "ChatPage should gate deliverable actions on whether 小娜 is still replying.",
);
assert.match(
  chatPageSource,
  /const pending = sending && idx === lastAssistantIdx[\s\S]*pending: sending/,
  "Only the in-flight turn's deliverable should be marked pending; finished files stay ready.",
);
assert.match(
  workspacePanelSource,
  /disabled=\{busy && Boolean\(item\.pending\)\}/,
  "Deliverable cards should only disable the file still being produced, not finished ones.",
);
assert.doesNotMatch(
  workspacePanelSource,
  /className="mt-3 grid gap-/,
  "Workspace stacks must use grid-cols-1 (minmax(0,1fr)); a bare auto-column grid lets long filenames blow the card past the panel.",
);
assert.match(
  workspacePanelSource,
  /setMode\("work"\)[\s\S]*setMode\("academy"\)/,
  "Right rail should offer a WORK / ACADEMY mode switch instead of nesting work inside academy.",
);
assert.match(
  workspacePanelSource,
  /mode === "work" \? \([\s\S]*workspace\.deliverables[\s\S]*\) : \([\s\S]*workspace\.reportPpt/,
  "WORK mode should show deliverables; ACADEMY mode should show the PPT/math launchpad.",
);
assert.match(
  workspacePanelSource,
  /kq-workspace-panel flex w-\[264px\] shrink-0/,
  "The right rail keeps a stable width so widening can never push it off a narrow window.",
);
assert.doesNotMatch(
  workspacePanelSource,
  /activity\.map/,
  "Workspace panel should not re-display the agent activity feed that already lives in AgentProgress.",
);

assert.doesNotMatch(
  workspacePanelSource,
  /workspace\.quickActions/,
  "Workspace panel should replace the generic Quick Actions heading with explicit groups.",
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
  /kabuqina_boot\.svg[\s\S]*kq-empty-title[\s\S]*\u6162\u6162\u6765\uff0c\u5c0f\u5a1c\u966a\u4f60\u6574\u7406\u601d\u8def/,
  "The empty chat state should show the hero asset, the product name title, then the greeting.",
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

assert.doesNotMatch(
  chatInputSource,
  /kq-input-footer/,
  "The composer keyboard-hint footer was intentionally removed per the Claude Design mockup.",
);

assert.match(
  chatInputSource,
  /syncTextareaHeight[\s\S]*scrollHeight[\s\S]*requestAnimationFrame/,
  "The chat composer should auto-grow so long prompts remain visible while typing.",
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

assert.match(messageListSource, /kq-empty-action\b/);
assert.match(messageListSource, /strokeWidth=\{2\.25\}/);
assert.match(
  messageListSource,
  /kq-color-icon-book[\s\S]*kq-color-icon-folder[\s\S]*kq-color-icon-alarm[\s\S]*kq-color-icon-pen/,
  "Empty-state quick actions should use unified colorful icon strokes.",
);

assert.match(
  messageListSource,
  /gridTemplateColumns: "1fr 1fr"[\s\S]*maxWidth: "380px"/,
  "Empty-state quick actions use a compact two-column grid capped at 380px so they fit narrow screens.",
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

// Regression: under StrictMode the render effect runs mount->cleanup->mount.
// The pptx_render reply must be guarded by a respondedRef that survives cleanup,
// never by a per-effect `cancelled` flag — otherwise the only reply is suppressed
// and the agent hits the 300s interaction timeout (pptx_render_cancelled).
assert.match(
  messageListSource,
  /respondedRef[\s\S]*renderDeckToBase64[\s\S]*onRespond\("rendered"/,
  "PptxRenderCard must reply via a respondedRef that survives StrictMode effect cleanup.",
);
assert.match(
  messageListSource,
  /const \{ base64, slideCount, audit \} = await renderDeckToBase64\(deck\)[\s\S]*pptx_render_audit: audit/,
  "PptxRenderCard should return render audit metadata so the agent can report the actual visual master and palette source.",
);
assert.doesNotMatch(
  messageListSource,
  /let cancelled = false;[\s\S]*onRespond\("rendered"/,
  "PptxRenderCard must not gate its render reply on a per-effect cancelled flag.",
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
  useChatStateSource,
  /readPersistedSession[\s\S]*restorePersistedSession/,
  "Chat state should expose a route-remount restore path for the last active session.",
);
assert.match(
  chatPageSource,
  /restorePersistedSession[\s\S]*sessions[\s\S]*listLoading/,
  "ChatPage should restore the active session after returning from Settings or Capabilities.",
);
assert.match(
  sendMessageSource,
  /persistActiveSessionId\(sessionForSend\)/,
  "New chat sends should persist the generated session id before route changes can unmount ChatPage.",
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
  workspacePanelSource,
  /kq-section-heading[\s\S]*h-1\.5 w-1\.5 shrink-0 rounded-full/,
  "Workspace section headings should use a small round dot accent instead of heavy lavender pills.",
);

assert.match(
  sidebarSource,
  /onExport[\s\S]*chat\.exportButton/,
  "Sidebar common actions should include Export Chat.",
);

const exportPageSource = fs.readFileSync(new URL("../advanced/Export.tsx", import.meta.url), "utf8");
const chatExportSource = fs.readFileSync(new URL("./chatExport.ts", import.meta.url), "utf8");
for (const fn of [
  "buildExportJson",
  "buildExportMarkdown",
  "buildExportText",
  "buildExportHtml",
  "exportLabelsForLocale",
]) {
  assert.match(
    exportPageSource,
    new RegExp(fn),
    `Export page should build dialogue exports via the ${fn} chatExport helper.`,
  );
}
assert.match(exportPageSource, /\(\["json", "markdown", "text", "pdf"\] as ExportFormat\[\]\)/);
assert.match(exportPageSource, /cmd_write_pdf_from_html/);
assert.match(chatExportSource, /parseDeskUserContent[\s\S]*speaker: labels\.productName/);
assert.doesNotMatch(chatExportSource, /Hermes|hermesdesk-export/i);

assert.match(
  sidebarSource,
  /onOpenWorkspace[\s\S]*kq-color-icon-folder[\s\S]*workspaceOpenWorkspace[\s\S]*onOpenScheduledTasks[\s\S]*kq-color-icon-alarm[\s\S]*cron\.title[\s\S]*onOrganizeDesktop[\s\S]*workspaceOrganizeDesktop[\s\S]*onExport[\s\S]*kq-color-icon-download[\s\S]*chat\.exportButton/,
  "Sidebar common actions should use colorful icons with open workspace first.",
);

for (const structureId of ["course_report", "paper_report", "code_defense"]) {
  assert.ok(
    workspacePanelSource.includes(structureId),
    `Workspace quick actions should target the ${structureId} PPT structure by id.`,
  );
}
assert.doesNotMatch(
  workspacePanelSource,
  /workspacePrecisePdf|precisePdfPrompt/,
  "Workspace quick actions should not expose a standalone Precise PDF shortcut.",
);

// The canonical planner rules (slide_type / layout vocabulary, placeholder
// discipline, per-structure must-cover outlines) now live in the agent system
// prompt (hermes_core build_deliverable_planner_prompt), shared by the desk and
// gateway children. The thin web prompt only defers to that four-layer flow.
assert.match(
  workspacePanelSource,
  /pptFlowReminder[\s\S]*material_index_build[\s\S]*review_outline[\s\S]*pptx_write/,
  "Student PPT quick actions should defer to the four-layer flow (material index → review → write).",
);
assert.doesNotMatch(
  workspacePanelSource,
  /screenshot_placeholder|chart_placeholder|comparison_cards|section_divider/,
  "Planner slide_type/layout vocabulary should be sunk into the system prompt, not duplicated in WorkspacePanel.",
);

assert.match(
  visualMastersSource,
  /PPT_VISUAL_MASTERS[\s\S]*soft_editorial[\s\S]*blue_professional[\s\S]*signal[\s\S]*neo_grid_bold[\s\S]*editorial_forest/,
  "Shared visual masters module should expose the generated visual masters.",
);
assert.match(
  visualMastersSource,
  /blue_professional[\s\S]*#FDFAE7[\s\S]*#1E2BFA[\s\S]*neo_grid_bold[\s\S]*#E6FF3D[\s\S]*editorial_forest[\s\S]*#2E4A2A/,
  "Student PPT visual master cards should use palette tokens from the actual visual master metadata.",
);
assert.match(
  workspacePanelSource,
  /import \{ PPT_VISUAL_MASTERS[\s\S]*from "\.\/pptx\/visualMasters"/,
  "WorkspacePanel should consume the shared visual masters module.",
);
assert.match(
  visualMastersSource,
  /export interface VisualMasterV2[\s\S]*typography[\s\S]*spacing[\s\S]*decorations[\s\S]*layouts/,
  "Visual masters should expose typography, spacing, decorations, and per-layout recipes.",
);
assert.match(
  visualMastersSource,
  /export interface VisualMasterV2[\s\S]*components[\s\S]*flow[\s\S]*table[\s\S]*media/,
  "Visual masters should expose component-level recipes for flows, tables, and media placeholders.",
);
assert.match(
  visualMastersSource,
  /soft_editorial[\s\S]*components[\s\S]*flow[\s\S]*nodeFill[\s\S]*blue_professional[\s\S]*components[\s\S]*flow[\s\S]*nodeFill/,
  "Soft Editorial and Blue Professional should define their own flow component language, not share a generic white-box diagram.",
);
for (const layoutId of [
  "cover",
  "hero_statement",
  "standard_bullets",
  "two_column_bullets",
  "comparison_cards",
  "process_flow_horizontal",
  "process_flow_vertical",
  "data_table",
  "media_placeholder",
  "section_divider",
]) {
  assert.match(
    visualMastersSource,
    new RegExp(`${layoutId}[\\s\\S]*x[\\s\\S]*y[\\s\\S]*w[\\s\\S]*h`),
    `VisualMasterV2 should define a geometry recipe for ${layoutId}.`,
  );
}

// Per-slide layout engine: each page is designed via a reusable layout
// registry + content-driven chooseLayout (with optional planner hint).
const renderDeckSource = fs.readFileSync(
  new URL("./pptx/renderDeck.ts", import.meta.url),
  "utf8",
);
assert.match(
  renderDeckSource,
  /export function chooseLayout[\s\S]*const layoutId = chooseLayout\(spec\)[\s\S]*LAYOUTS\[layoutId\]\(ctx\)/,
  "renderDeck should pick a per-slide layout via chooseLayout and a layout registry.",
);
// Track D: chooseLayout honors model-provided design intent before content guessing.
assert.match(
  renderDeckSource,
  /spec\.emphasis\?\.kind === "quote"[\s\S]*spec\.emphasis\?\.kind === "stat"[\s\S]*spec\.metrics\?\.length/,
  "chooseLayout should route pull_quote / stat layouts from emphasis + metrics design intent.",
);
assert.match(
  renderDeckSource,
  /function statMetrics[\s\S]*if \(spec\.metrics\?\.length\)/,
  "statMetrics should prefer model-provided structured metrics over parsing bullet prose.",
);
assert.match(
  renderDeckSource,
  /interface DeckSlideSpec[\s\S]*metrics\?:[\s\S]*emphasis\?:/,
  "DeckSlideSpec should declare optional metrics and emphasis design-intent fields.",
);
assert.match(
  renderDeckSource,
  /master\.typography[\s\S]*master\.layouts\[layoutId\][\s\S]*layoutRecipe/,
  "renderDeck should consume VisualMasterV2 typography, spacing, decorations, and layout recipes.",
);
assert.match(
  renderDeckSource,
  /export interface RenderAudit[\s\S]*visualMasterId[\s\S]*paletteSource[\s\S]*slideLayouts[\s\S]*audit: RenderAudit/,
  "renderDeck should return an audit trail with the selected visual master, palette source, and per-slide layouts.",
);
assert.match(
  renderDeckSource,
  /master\.components\.flow[\s\S]*master\.components\.table[\s\S]*master\.components\.media/s,
  "Flow, table, and media layouts should be styled from the selected visual master's component recipes.",
);
assert.match(
  renderDeckSource,
  /function drawMiniChart[\s\S]*function renderChartSignal[\s\S]*drawMiniChart\(ctx, media, chartItems\(spec\)\)/s,
  "Chart-placeholder slides should render an editable signal chart instead of only a placeholder box.",
);
assert.match(
  renderDeckSource,
  /function renderEvidenceCards[\s\S]*renderTwoColumnBullets[\s\S]*renderEvidenceCards/s,
  "Two-column evidence pages should use master-styled evidence cards instead of plain bullet text blocks.",
);
assert.match(
  renderDeckSource,
  /function masterFontFaces[\s\S]*pptx\.theme = \{ headFontFace: fonts\.head[\s\S]*bodyFontFace: fonts\.body/s,
  "Built-in visual masters should set concrete PowerPoint theme fonts, not fall back to Office/Calibri.",
);
assert.match(
  visualMastersSource,
  /blue_professional[\s\S]*fontFace:\s*"Microsoft YaHei UI"/,
  "Blue Professional should define Office-safe Chinese font faces for its typography roles.",
);
assert.doesNotMatch(
  renderDeckSource,
  /const boxW = 2\.7, boxH = 1\.15, gap = 0\.4, top = 3\.2/,
  "Process layout geometry should come from the selected visual master, not a single hardcoded recipe.",
);
assert.doesNotMatch(
  renderDeckSource,
  /renderProcessFlow(?:Horizontal|Vertical)[\s\S]*fill: \{ color: "FFFFFF" \}[\s\S]*line: \{ color: p\.accent/,
  "Process layouts should not regress to a generic white-box flow style.",
);
for (const layoutId of [
  "hero_statement",
  "standard_bullets",
  "two_column_bullets",
  "comparison_cards",
  "process_flow_horizontal",
  "process_flow_vertical",
  "data_table",
  "media_placeholder",
  "section_divider",
]) {
  assert.ok(
    renderDeckSource.includes(layoutId),
    `renderDeck layout registry should define ${layoutId}.`,
  );
}
// Cover must give deck-level metadata (author/affiliation/date/citation) a home,
// so the planner never crams a byline into an agenda or content slide.
assert.match(
  renderDeckSource,
  /const meta = deck\.meta[\s\S]*meta\.author[\s\S]*meta\.affiliation[\s\S]*meta\.date[\s\S]*meta\.citation/,
  "addCover should render deck.meta byline + citation on the cover.",
);
// Route A: an uploaded school template supplies an inline palette/fonts override
// that takes precedence over the built-in visual master, per field.
assert.match(
  renderDeckSource,
  /const override = deck\.visual_master_palette[\s\S]*override\?\.background \?\? master\.palette\.background[\s\S]*pptx\.theme = \{ headFontFace/,
  "renderDeck should let an uploaded template's palette/fonts override the built-in master.",
);
assert.match(
  renderDeckSource,
  /const override = deck\.visual_master_palette[\s\S]*const master = getVisualMaster\(deck\.visual_master\)[\s\S]*master\.layouts\[layoutId\]/,
  "Uploaded template themes should override palette/fonts while keeping built-in layout recipes for VisualMasterV2.",
);
// Regression: accent2 is the 5th palette colour and must actually be DRAWN, not
// just extracted — every master's second signature colour should reach a slide.
assert.match(
  renderDeckSource,
  /fill: \{ color: p\.accent2 \}/,
  "renderDeck layouts must render the master's accent2 (e.g. rail cap / title underline), not drop it.",
);
assert.ok(
  (renderDeckSource.match(/\.accent2/g) || []).length >= 6,
  "accent2 should be used across multiple layouts (header, agenda, flow, comparison, hero, cover).",
);
assert.match(
  workspacePanelSource,
  /pptMasterPreviewStyle[\s\S]*--kq-ppt-bg[\s\S]*--kq-ppt-accent[\s\S]*style=\{pptMasterPreviewStyle\(master\)\}/,
  "Student PPT visual master previews should render from per-master palette data instead of stale CSS-only color classes.",
);

assert.match(workspacePanelSource, /workspacePptVisualMaster/, "Student PPT quick actions should label the visual master selector.");
assert.match(
  workspacePanelSource,
  /PptVisualMasterPreview[\s\S]*kq-ppt-master-preview[\s\S]*master=\{selectedPptVisualMaster\}/,
  "Student PPT visual master selection should include an immediate visual preview.",
);
assert.match(
  workspacePanelSource,
  /join\("\\n\\n"\)[\s\S]*pptFlowReminder[\s\S]*pptVisualMasterRule/,
  "Student PPT prompts should use paragraph breaks (intent + flow reminder + visual master).",
);
assert.match(
  workspacePanelSource,
  /pptx_write[\s\S]*visual_master[\s\S]*selectedPptVisualMaster\.id/,
  "Student PPT prompts should carry the selected visual_master into pptx_write.",
);

assert.match(
  agentProgressSource,
  /useState[\s\S]*collapsed[\s\S]*chat\.streamingWorking[\s\S]*progress\.steps\.length[\s\S]*ChevronDown/,
  "Agent progress should collapse dense streaming tool rows into a one-line working status.",
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
  /kq-reminder-card/,
  "Scheduled tasks entry should not regress to the old sidebar reminder card.",
);

assert.match(
  indexCssSource,
  /kq-titlebar[\s\S]*kq-titlebar-link-active/,
  "The chat CSS should define unified titlebar, readable workspace headings, and lavender footer toggle styling.",
);

assert.match(
  titleBarSource,
  /kq-titlebar-nav[\s\S]*kq-titlebar-companion-btn[\s\S]*kq-titlebar-companion-icon/,
  "The companion sparkle should sit in the centered titlebar nav.",
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
assert.match(chatPageReminderSource, /\/settings\/cron/);
