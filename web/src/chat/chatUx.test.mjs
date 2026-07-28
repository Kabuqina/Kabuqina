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
const drawerSource = fs.readFileSync(new URL("./ChatHistoryDrawer.tsx", import.meta.url), "utf8");
const messageListSource = fs.readFileSync(new URL("./ChatMessageList.tsx", import.meta.url), "utf8");
const outlineReviewModalSource = fs.readFileSync(new URL("./OutlineReviewModal.tsx", import.meta.url), "utf8");
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

assert.match(
  drawerSource,
  /onExport/,
  "Export chat should stay reachable from the history drawer.",
);

assert.doesNotMatch(
  drawerSource,
  /nav\("\/capabilities"\)|t\("capabilities\.title"\)/,
  "The retired capability catalog should not appear in the history drawer.",
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
const artAssetsSource = fs.readFileSync(new URL("../lib/artAssets.ts", import.meta.url), "utf8");
assert.match(
  chatMessageSource,
  /<AssistantAvatar/,
  "Assistant messages should render the mascot avatar beside the bubble.",
);
// 图形走 lib/artAssets.ts 这一个换装接缝（pre-art），不再硬编码路径字面量。
assert.match(assistantAvatarSource, /ART_ASSETS\.mascot[\s\S]*kq-assistant-avatar/);
assert.match(artAssetsSource, /mascot:\s*"\/kabuqina_mascot\.svg"/);

assert.doesNotMatch(
  chatMessageSource,
  /kq-user-avatar|<User\b|user avatar/i,
  "User messages should stay as clean bubbles without a user avatar.",
);

const chatPageSource = fs.readFileSync(new URL("./ChatPage.tsx", import.meta.url), "utf8");
const chatApiSource = fs.readFileSync(new URL("./chat-api.ts", import.meta.url), "utf8");
const sendMessageSource = fs.readFileSync(new URL("./hooks/useSendMessage.ts", import.meta.url), "utf8");
const desktopApiSource = fs.readFileSync(new URL("./desktop-organizer-api.ts", import.meta.url), "utf8");
const workspacePanelSource = fs.readFileSync(
  new URL("./WorkspacePanel.tsx", import.meta.url),
  "utf8",
);
// Shared section primitives were extracted from WorkspacePanel into
// ./workspaceSection so feature modules (e.g. ./study) can reuse them.
const workspaceSectionSource = fs.readFileSync(
  new URL("./workspaceSection.tsx", import.meta.url),
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
  "Confirmed desktop organizing should add a visible user action and assistant result to chat.",
);

assert.match(
  chatPageSource,
  /handleOrganizeDesktop[\s\S]*const ok = await confirm\(\{[\s\S]*desktopOrganizer\.confirmTitle[\s\S]*desktopOrganizer\.confirmBody[\s\S]*desktopOrganizer\.confirmApply[\s\S]*desktopOrganizer\.confirmCancel[\s\S]*tone: "warning"[\s\S]*if \(!ok\) return;[\s\S]*setMessages[\s\S]*runDesktopOrganize\(locale\)/,
  "Desktop organizing must show the shared confirmation dialog before transcript updates or cmd_desktop_organize_run.",
);

assert.match(
  stringsSource,
  /confirmTitle:[\s\S]*confirmBody:[\s\S]*confirmApply:[\s\S]*confirmCancel:/,
  "Desktop organizing confirmation copy should be localized.",
);

// S5：Chat 是刻意极简的自由对话空间——单张居中对话纸，两条常驻侧栏都退场。
assert.match(
  chatPageSource,
  /ChatHistoryDrawer[\s\S]*open=\{historyOpen\}/,
  "ChatPage should keep session history in an on-demand drawer, not a standing rail.",
);

assert.doesNotMatch(
  chatPageSource,
  /ChatSidebar|useWorkbenchLayout|toggleFocusMode/,
  "The standing left rail and focus-mode toggle are gone: the minimal chat is focus mode.",
);

// 换布局不等于砍能力：工作台面板改成按需打开，入口挪到 composer 上。
assert.match(
  chatPageSource,
  /WorkspacePanel/,
  "ChatPage should still be able to open the workspace panel.",
);

assert.match(
  chatPageSource,
  /onOpenWorkspacePanel=\{\(\) => setWorkspaceOpen\(true\)\}/,
  "The workspace panel entry should live on the composer now that the right rail is gone.",
);

assert.match(
  stringsSource,
  /workspaceModeReport:\s*"REPORT"/,
  "The launchpad tab label is REPORT (ACADEMY was renamed in the v0.3.0 reorg).",
);
assert.doesNotMatch(
  stringsSource,
  /workspaceTitle:\s*"ACADEMY"|workspaceMathAbility:/,
  "The old ACADEMY tab title and Math-ability keys must not linger in the locales.",
);
assert.match(
  stringsSource,
  /workspaceMathCode:\s*"数学与代码"/,
  "The math section is titled 数学与代码 inside STUDY.",
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

// 侧栏上那几个工具没有别处可去，收进抽屉底部——不显眼，但都还在。
assert.match(
  drawerSource,
  /onOpenScheduledTasks[\s\S]*onOpenWorkspace[\s\S]*onOrganizeDesktop[\s\S]*onExport/,
  "The drawer should carry the utilities that used to live in the left rail.",
);

assert.match(
  drawerSource,
  /kq-chat-drawer-new[\s\S]*chat\.newChat/,
  "New chat should stay at the top of the drawer.",
);

assert.match(
  drawerSource,
  /deriveSessionPresentation/,
  "The drawer should reuse the shared session presentation (labels, grouping, reminder log).",
);

assert.match(
  drawerSource,
  /onDeleteSession/,
  "Deleting a conversation should stay reachable after the rail was retired.",
);

// 三类会话进同一份列表，来源只用低强调标签辨认，没有并列的作用域标签页。
assert.match(
  drawerSource,
  /kq-chat-drawer-origin/,
  "Scoped conversations should be marked with a low-emphasis origin tag in the unified list.",
);

assert.doesNotMatch(
  chatPageSource,
  /chat\.activeWork/,
  "The center header should not render the redundant active-work label.",
);

assert.doesNotMatch(
  chatPageSource,
  /DesktopOrganizerModal|desktopOrganizerOpen|setDesktopOrganizerOpen/,
  "Desktop organizing should reuse the shared confirm dialog, not the removed organizer preview modal flow.",
);

assert.match(
  desktopApiSource,
  /cmd_desktop_organize_run/,
  "Desktop organizing should call the one-click Tauri command.",
);

assert.match(
  workspacePanelSource,
  /workspace\.reportPpt[\s\S]*workspacePaperToPpt[\s\S]*workspaceCourseToPpt[\s\S]*workspaceCodeToPpt[\s\S]*workspaceSandtableToPpt/,
  "Workspace panel should group the four report PPT workflows under Generate Report PPT, paper first.",
);
assert.match(
  workspacePanelSource,
  /import \{ open \} from "@tauri-apps\/plugin-dialog"/,
  "Directory-based PPT workflows should use the native Tauri folder picker.",
);
assert.match(
  workspacePanelSource,
  /function buildPptDirectoryBase[\s\S]*材料目录：\$\{folderPath\}[\s\S]*递归读取[\s\S]*material_index_build/,
  "Code and sandtable PPT prompts should carry the chosen material directory and require recursive indexing.",
);
assert.match(
  workspacePanelSource,
  /open\(\{[\s\S]*directory:\s*true[\s\S]*multiple:\s*false[\s\S]*workspaceChoosePptMaterialFolder/,
  "Directory-based PPT workflows should open a single-folder picker with a specific title.",
);
assert.match(
  workspacePanelSource,
  /setPptModal\(\{ base: paperToPptBase \}\)[\s\S]*setPptModal\(\{ base: courseToPptBase \}\)[\s\S]*pickPptMaterialFolder\(codeToPptBase\)[\s\S]*workspaceCodeToPpt[\s\S]*pickPptMaterialFolder\(sandtableToPptBase\)[\s\S]*workspaceSandtableToPpt/,
  "Only code-project and sandtable PPT workflows should require choosing a materials folder.",
);
assert.match(
  stringsSource,
  /workspaceChoosePptMaterialFolder:\s*"选择材料目录…"/,
  "PPT material folder picker should have localized zh copy.",
);
assert.match(
  stringsSource,
  /workspaceChoosePptMaterialFolder:\s*"Choose materials folder…"/,
  "PPT material folder picker should have localized en copy.",
);

assert.match(
  workspacePanelSource,
  /workspace\.mathAbility[\s\S]*workspaceFormulaToCode[\s\S]*workspaceCodeToFormula[\s\S]*workspaceMathFormulaExtract/,
  "Workspace panel should group code/formula conversion and formula extraction under Math & Code, formula-to-code first.",
);
// ACADEMY→REPORT reorg (docs/superpowers/specs/2026-07-05-study-math-code-practice-design.md §6.1):
// math is a learning function, so its section renders inside the STUDY branch,
// after the first-class notebook entry; the report branch keeps only PPT.
assert.match(
  workspacePanelSource,
  /<OpenStudyLink \/>[\s\S]*workspace\.mathAbility/,
  "Math & Code must live in the STUDY tab, below the first-class notebook entry.",
);
assert.doesNotMatch(
  workspacePanelSource,
  /"academy"/,
  "The academy mode id is gone — the launchpad tab is REPORT now.",
);
// The math prompts follow the STUDY conversational contract plus the
// answer-then-teach hook (knowledge points + offer of a variant round).
assert.match(
  workspacePanelSource,
  /一次只问一个问题[\s\S]*变式练习[\s\S]*请不要使用 emoji/,
  "Math & Code prompts should pace one question per turn and end with the variant-practice hook.",
);
assert.match(
  workspacePanelSource,
  /反向练一遍[\s\S]*我拒绝就不再追问/,
  "Code-to-formula should offer reverse practice without nagging after refusal.",
);
assert.match(
  workspacePanelSource,
  /semantic_contract[\s\S]*定义域\/取值范围[\s\S]*a < c < b[\s\S]*needs_human_check/,
  "Formula-to-code prompt should require semantic contract checks, including open interval constraints.",
);

assert.doesNotMatch(
  workspacePanelSource,
  /workspace\.otherCommon|cron\.title|workspaceOpenWorkspace|workspaceOrganizeDesktop|chat\.exportButton/,
  "Workspace panel should not keep non-launchpad common actions.",
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
  /setMode\("work"\)[\s\S]*setMode\("study"\)[\s\S]*setMode\("report"\)/,
  "Right rail should offer a WORK / STUDY / REPORT mode switch instead of nesting work inside the launchpad.",
);
assert.match(
  workspacePanelSource,
  /workspace\.deliverables[\s\S]*workspace\.reportPpt[\s\S]*workspace\.mathAbility/,
  "Source order: WORK deliverables, then REPORT's PPT launchpad, then STUDY's Math & Code.",
);
assert.match(
  workspacePanelSource,
  /mode === "study"[\s\S]*<OpenStudyLink \/>/,
  "STUDY mode should show the first-class notebook entry.",
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

// 全窗口只有一条横条：产品面上那条是 AppShell 的页眉，其余页面才用这条标题栏，
// 且它只剩品牌 + 同一个 WindowControls（S2）。
assert.doesNotMatch(
  titleBarSource,
  /kq-titlebar-nav|kq-titlebar-link|to="\/study"|to="\/chat"/,
  "The window title bar must not carry a second product navigation.",
);

assert.match(
  titleBarSource,
  /<WindowControls \/>/,
  "The window title bar should render the shared window controls.",
);

const appShellSource = fs.readFileSync(new URL("../shell/AppShell.tsx", import.meta.url), "utf8");
assert.match(
  appShellSource,
  /data-tauri-drag-region[\s\S]*<WindowControls \/>/,
  "On product surfaces the shell header is the title bar: draggable, with the window controls at its right end.",
);

assert.match(
  titleBarSource,
  /kq-titlebar/,
  "The title bar should use the Kabuqina lavender system instead of the default blue/zinc treatment.",
);

for (const className of ["kq-titlebar-brand", "kq-titlebar"]) {
  assert.match(titleBarSource, new RegExp(className), `Title bar should include ${className}.`);
}

assert.match(
  messageListSource,
  /ART_ASSETS\.boot[\s\S]*kq-empty-title[\s\S]*\u6162\u6162\u6765\uff0c\u5c0f\u5a1c\u966a\u4f60\u6574\u7406\u601d\u8def/,
  "The empty chat state should show the hero asset, the product name title, then the greeting.",
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

// v0.5.0 起不再分权限层（owner 2026-07-27）：能力默认全开，风险动作仍逐次确认。
// 顶栏与聊天页都不该再出现 power-mode 开关。
assert.doesNotMatch(titleBarSource, /useTogglePowerUser|powerUser|settings\.powerTitle/);
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
assert.doesNotMatch(
  titleBarSource,
  /kq-titlebar-power/,
  "The retired power-mode toggle should stay out of the title bar.",
);
assert.doesNotMatch(
  titleBarSource,
  /\/capabilities|capabilities\.title/,
  "The retired capability catalog should stay out of the title bar.",
);
assert.doesNotMatch(
  fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8"),
  /CapabilitiesPage|path="\/capabilities"/,
  "The retired capability catalog route should not be bundled.",
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
  /outline_review[\s\S]*OutlineReviewModal/s,
  "Chat should render OutlineReviewModal for outline_review interactions.",
);
assert.match(
  outlineReviewModalSource,
  /通过[\s\S]*补充要求[\s\S]*自行编辑/s,
  "OutlineReviewModal should keep the original action button order: approve, refine, edit.",
);
assert.match(
  outlineReviewModalSource,
  /重新生成/s,
  "OutlineReviewModal should expose the refine action inside the refine panel.",
);
assert.match(
  outlineReviewModalSource,
  /保存并生成/s,
  "OutlineReviewModal should expose the edit action inside the edit panel.",
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
  workspaceSectionSource,
  /kq-workspace-card/,
  "Workspace sections should render as lavender-tinted cards.",
);

assert.match(
  workspaceSectionSource,
  /kq-section-heading[\s\S]*h-1\.5 w-1\.5 shrink-0 rounded-full/,
  "Workspace section headings should use a small round dot accent instead of heavy lavender pills.",
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
assert.match(
  messageListSource,
  /shouldDisplayAgentProgress\(progress\)/,
  "ChatMessageList should show the working/tool bubble only when a turn has actual tool activity.",
);
assert.match(
  messageListSource,
  /pendingAssistant && pendingVisibleText &&/,
  "Placeholder-only assistant stream text should not render as a reply bubble before real text arrives.",
);
assert.match(
  messageListSource,
  /sending && !showAgentProgress && !pendingVisibleText && <TypingIndicator \/>/,
  "Non-tool turns should keep the ordinary waiting bubble until assistant text starts streaming.",
);

assert.doesNotMatch(
  workspacePanelSource,
  /workspaceAddFile|workspaceCapture|FilePlus2|Camera/,
  "Workspace quick actions should not show unfinished Add File or Screenshot actions.",
);

assert.match(
  indexCssSource,
  /kq-titlebar[\s\S]*kq-window-controls/,
  "The shell CSS should define the title bar and the shared window controls.",
);

// S5：单张居中对话纸 + 按需抽屉，两条常驻侧栏都退场。
assert.match(
  indexCssSource,
  /\.kq-chat-paper \{[\s\S]*max-width[\s\S]*margin: 0 auto/,
  "Chat should be one centered conversation paper.",
);

const windowControlsSource = fs.readFileSync(new URL("../components/WindowControls.tsx", import.meta.url), "utf8");
assert.match(
  windowControlsSource,
  /kq-titlebar-companion-btn[\s\S]*kq-titlebar-companion-icon/,
  "The companion sparkle rides with the window controls, on whichever bar carries them.",
);
assert.match(windowControlsSource, /cmd_show_companion/);
assert.match(indexCssSource, /kq-titlebar-companion-btn/);
assert.match(indexCssSource, /kq-titlebar-power/);
assert.match(indexCssSource, /--radius-shell-lg:\s*0\.75rem/);
assert.match(indexCssSource, /kq-workspace-card[\s\S]*border-radius:\s*var\(--radius-shell-lg\)/);
assert.match(indexCssSource, /hd-glass-subtle[\s\S]*border-radius:\s*var\(--radius-shell-lg\)/);

const {
  getCachedKabuqinaReadiness,
  snapshotFromBootState,
  updateKabuqinaReadinessCache,
} = await importTs("./kabuqinaReadinessCache.ts");
const useKabuqinaReadinessSource = fs.readFileSync(
  new URL("./hooks/useKabuqinaReadiness.ts", import.meta.url),
  "utf8",
);

assert.deepEqual(getCachedKabuqinaReadiness(), {
  kabuqinaReady: false,
  kabuqinaWarming: false,
  bootErr: null,
});

assert.deepEqual(snapshotFromBootState({ port: 12345, warming: false }), {
  kabuqinaReady: true,
  kabuqinaWarming: false,
  bootErr: null,
});

assert.deepEqual(updateKabuqinaReadinessCache({ port: 12345, warming: false }, null), {
  kabuqinaReady: true,
  kabuqinaWarming: false,
  bootErr: null,
});

assert.deepEqual(getCachedKabuqinaReadiness(), {
  kabuqinaReady: true,
  kabuqinaWarming: false,
  bootErr: null,
});

assert.match(
  useKabuqinaReadinessSource,
  /getCachedKabuqinaReadiness[\s\S]*updateKabuqinaReadinessCache/,
  "Chat readiness hook should seed UI from a route-surviving cache.",
);

const reminderSessionSource = fs.readFileSync(new URL("./reminderSession.ts", import.meta.url), "utf8");
const chatPageReminderSource = fs.readFileSync(new URL("./ChatPage.tsx", import.meta.url), "utf8");
assert.match(reminderSessionSource, /hermesdesk-reminders/);
assert.match(chatPageReminderSource, /openReminderSession[\s\S]*REMINDER_SESSION_ID/);
assert.match(chatPageReminderSource, /\/settings\/cron/);


// ── kq-kp knowledge-point protocol ──────────────────────────────────────────
// Assistant messages strip the trailing kq-kp block from the prose (also for
// copy/TTS) and render it as chips that feed the spaced-repetition deck. The
// parsing contract itself is covered by knowledgePoints.test.mjs.
assert.match(
  chatMessageSource,
  /splitKnowledgePoints\(text\)/,
  "ChatMessage should split kq-kp knowledge points out of assistant text.",
);
assert.match(
  chatMessageSource,
  /<ChatMarkdown text=\{body\} \/>/,
  "ChatMessage should render the stripped body, never the raw kq-kp block.",
);
assert.match(
  chatMessageSource,
  /points\.length > 0 && <KnowledgePointChips points=\{points\} \/>/,
  "ChatMessage should render knowledge-point chips only when a message has points.",
);
assert.match(
  chatMessageSource,
  /<AssistantMessageFooter text=\{body\}/,
  "Copy/TTS should use the stripped body, not the raw text.",
);
const kpChipsSource = fs.readFileSync(new URL("./study/KnowledgePointChips.tsx", import.meta.url), "utf8");
assert.match(
  kpChipsSource,
  /cmdStudyFlashcardCapture/,
  "Knowledge-point chips should capture cards through the trusted learning.db API.",
);
assert.doesNotMatch(
  kpChipsSource,
  /localStorage|FLASHCARD_STORAGE_KEY/,
  "Knowledge-point chips should not write new cards to legacy localStorage.",
);
assert.match(
  kpChipsSource,
  /if \(unavailable\)[\s\S]*captureIndex\.forceRefresh\(\)/,
  "Unavailable knowledge-point chips should offer an explicit storage retry.",
);
assert.match(
  kpChipsSource,
  /disabled=\{added \|\| saving \|\| loading\}/,
  "Knowledge-point chips should block capture while the shared refresh is pending.",
);
assert.match(
  kpChipsSource,
  /aria-busy=\{loading \|\| saving\}/,
  "Knowledge-point chips should expose retry/save progress to assistive technology.",
);
assert.doesNotMatch(workspacePanelSource, /StudySection/, "The duplicate legacy STUDY sidebar surface should be retired.");
assert.match(
  workspacePanelSource,
  /mode === "study"[\s\S]*<OpenStudyLink \/>[\s\S]*workspace\.mathAbility/,
  "STUDY mode should keep one first-class notebook entry followed by Math & Code.",
);
