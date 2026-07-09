// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { PROVIDERS } from "../../lib/providers";
import type { Localized, OptionConfigField, PostPassSectionId, SetupCatalogOption } from "./optionTypes";

const L = (zh: string, en: string) => ({ zh, en });

/** Reusable field factory (all optional in wizard: empty = use Hermes / skip). */
const F = (
  id: string,
  label: Localized,
  placeholder: Localized,
  kind: OptionConfigField["kind"] = "text",
  optional = true
): OptionConfigField => ({ id, label, placeholder, kind, optional });

export const CATALOG_TTS: SetupCatalogOption[] = [
  {
    id: "edge",
    name: L("Edge TTS", "Edge TTS"),
    defaultHint: L("default：无额外 key", "Default: no extra key"),
    isDefault: true,
  },
  {
    id: "elevenlabs",
    name: L("ElevenLabs", "ElevenLabs"),
    defaultHint: L("ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"),
    configFields: [
      F(
        "ELEVENLABS_API_KEY",
        L("ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY"),
        L("在厂商控制台创建后粘贴", "From ElevenLabs console"),
        "password"
      ),
    ],
  },
  {
    id: "xai",
    name: L("xAI TTS (Grok)", "xAI TTS (Grok)"),
    defaultHint: L("XAI_API_KEY", "XAI_API_KEY"),
    configFields: [F("XAI_API_KEY", L("XAI_API_KEY", "XAI_API_KEY"), L("xAI 控制台", "xAI console"), "password")],
  },
  {
    id: "minimax",
    name: L("MiniMax TTS", "MiniMax TTS"),
    defaultHint: L("MINIMAX_API_KEY", "MINIMAX_API_KEY"),
    configFields: [F("MINIMAX_API_KEY", L("MINIMAX_API_KEY", "MINIMAX_API_KEY"), L("选填", "optional"), "password")],
  },
  {
    id: "mistral_tts",
    name: L("Mistral Voxtral TTS", "Mistral Voxtral TTS"),
    defaultHint: L("MISTRAL_API_KEY", "MISTRAL_API_KEY"),
    configFields: [F("MISTRAL_API_KEY", L("MISTRAL_API_KEY", "MISTRAL_API_KEY"), L("选填", "optional"), "password")],
  },
  {
    id: "neutts",
    name: L("NeuTTS（本机）", "NeuTTS (on-device)"),
    defaultHint: L("本机包与系统依赖，可空置后装", "Local packages; can skip here"),
  },
  {
    id: "xfyun",
    name: L("讯飞语音合成（在线）", "iFlytek TTS (online)"),
    defaultHint: L("科大讯飞在线合成，需三件套", "iFlytek online TTS, needs 3 keys"),
    configFields: [
      F("XFYUN_APPID", L("XFYUN_APPID", "XFYUN_APPID"), L("讯飞开放平台应用 APPID", "iFlytek console APPID"), "text"),
      F("XFYUN_API_KEY", L("XFYUN_API_KEY", "XFYUN_API_KEY"), L("讯飞开放平台 APIKey", "iFlytek console APIKey"), "password"),
      F("XFYUN_API_SECRET", L("XFYUN_API_SECRET", "XFYUN_API_SECRET"), L("讯飞开放平台 APISecret", "iFlytek console APISecret"), "password"),
    ],
  },
];

/**
 * STT (speech-to-text) providers exposed in the wizard. Row `id`s match the
 * canonical `stt.provider` strings recognised by `tools.transcription_tools`,
 * so the wizard can write them to `config.yaml` directly without a UI→backend
 * id mapping. The one exception is ``local_whisper_cpp`` which is a UI-only
 * label for the bundled whisper.cpp wrapper — ``SectionPlaceholderStep``
 * maps it to ``local_command`` before persisting.
 */
export const CATALOG_STT: SetupCatalogOption[] = [
  {
    id: "local_whisper_cpp",
    name: L("本地识别（推荐）", "Local (recommended)"),
    defaultHint: L(
      "无需 API Key，首次使用约 60MB 模型一次性下载。",
      "No API key. Downloads ~60 MB on first use, then runs offline."
    ),
    isDefault: true,
  },
  {
    id: "groq",
    name: L("Groq Whisper（云端，需 Key）", "Groq Whisper (cloud, requires key)"),
    defaultHint: L("免费额度高的云端备选", "Free-tier cloud alternative"),
    configFields: [
      F(
        "GROQ_API_KEY",
        L("GROQ_API_KEY", "GROQ_API_KEY"),
        L("https://console.groq.com 免费创建", "Create at https://console.groq.com"),
        "password"
      ),
    ],
  },
  {
    id: "mistral",
    name: L("Mistral Voxtral STT", "Mistral Voxtral STT"),
    defaultHint: L("MISTRAL_API_KEY", "MISTRAL_API_KEY"),
    configFields: [
      F("MISTRAL_API_KEY", L("MISTRAL_API_KEY", "MISTRAL_API_KEY"), L("Mistral 控制台", "Mistral console"), "password"),
    ],
  },
  {
    id: "xai",
    name: L("xAI Grok STT", "xAI Grok STT"),
    defaultHint: L("XAI_API_KEY", "XAI_API_KEY"),
    configFields: [
      F("XAI_API_KEY", L("XAI_API_KEY", "XAI_API_KEY"), L("xAI 控制台", "xAI console"), "password"),
    ],
  },
  {
    id: "xfyun",
    name: L("讯飞语音听写（在线）", "iFlytek IAT (online)"),
    defaultHint: L("科大讯飞在线听写，需三件套", "iFlytek online dictation, needs 3 keys"),
    configFields: [
      F("XFYUN_APPID", L("XFYUN_APPID", "XFYUN_APPID"), L("讯飞开放平台应用 APPID", "iFlytek console APPID"), "text"),
      F("XFYUN_API_KEY", L("XFYUN_API_KEY", "XFYUN_API_KEY"), L("讯飞开放平台 APIKey", "iFlytek console APIKey"), "password"),
      F("XFYUN_API_SECRET", L("XFYUN_API_SECRET", "XFYUN_API_SECRET"), L("讯飞开放平台 APISecret", "iFlytek console APISecret"), "password"),
    ],
  },
  {
    id: "local",
    name: L("本地 faster-whisper", "Local faster-whisper"),
    defaultHint: L("零成本；需先在本机安装 faster-whisper", "Free; requires faster-whisper installed locally"),
  },
  {
    id: "local_command",
    name: L("本地外部命令", "Local external command"),
    defaultHint: L("HERMES_LOCAL_STT_COMMAND", "HERMES_LOCAL_STT_COMMAND"),
    configFields: [
      F(
        "HERMES_LOCAL_STT_COMMAND",
        L("HERMES_LOCAL_STT_COMMAND", "HERMES_LOCAL_STT_COMMAND"),
        L("如 whisper 或 whisper.cpp 路径", "e.g. path to whisper / whisper.cpp"),
        "text"
      ),
      F(
        "HERMES_LOCAL_STT_LANGUAGE",
        L("HERMES_LOCAL_STT_LANGUAGE（可空）", "HERMES_LOCAL_STT_LANGUAGE (optional)"),
        L("如 zh、en", "e.g. zh, en"),
        "text"
      ),
    ],
  },
];

export const CATALOG_TERMINAL: SetupCatalogOption[] = [
  {
    id: "local",
    name: L("Local", "Local"),
    defaultHint: L("default：local", "default: local"),
    isDefault: true,
    configFields: [
      F(
        "terminal_cwd_messaging",
        L("消息会话工作目录（可空）", "Messaging working directory (optional)"),
        L("例如用户主目录路径", "e.g. home path"),
        "text"
      ),
    ],
  },
  {
    id: "docker",
    name: L("Docker", "Docker"),
    defaultHint: L("TERMINAL_DOCKER_IMAGE 等", "TERMINAL_DOCKER_IMAGE, …"),
    configFields: [
      F(
        "TERMINAL_DOCKER_IMAGE",
        L("TERMINAL_DOCKER_IMAGE", "TERMINAL_DOCKER_IMAGE"),
        L("例：nikolaik/python-nodejs:…", "e.g. nikolaik/…"),
        "text"
      ),
    ],
  },
  {
    id: "modal",
    name: L("Modal", "Modal"),
    defaultHint: L("MODAL_TOKEN_ID / MODAL_TOKEN_SECRET 等", "MODAL_TOKEN_ID / MODAL_TOKEN_SECRET, …"),
    configFields: [
      F("MODAL_TOKEN_ID", L("MODAL_TOKEN_ID", "MODAL_TOKEN_ID"), L("Modal 设置页", "Modal settings"), "password"),
      F("MODAL_TOKEN_SECRET", L("MODAL_TOKEN_SECRET", "MODAL_TOKEN_SECRET"), L("与 ID 成对", "with token id"), "password"),
    ],
  },
  {
    id: "daytona",
    name: L("Daytona", "Daytona"),
    defaultHint: L("DAYTONA_API_KEY", "DAYTONA_API_KEY"),
    configFields: [F("DAYTONA_API_KEY", L("DAYTONA_API_KEY", "DAYTONA_API_KEY"), L("Daytona 控制台", "Daytona console"), "password")],
  },
  {
    id: "ssh",
    name: L("SSH 远端", "SSH remote"),
    defaultHint: L("TERMINAL_SSH_HOST / USER / …", "TERMINAL_SSH_HOST / USER / …"),
    configFields: [
      F("TERMINAL_SSH_HOST", L("TERMINAL_SSH_HOST", "TERMINAL_SSH_HOST"), L("主机名或 IP", "hostname or IP"), "text"),
      F("TERMINAL_SSH_USER", L("TERMINAL_SSH_USER", "TERMINAL_SSH_USER"), L("SSH 用户", "SSH user"), "text"),
      F("TERMINAL_SSH_PORT", L("TERMINAL_SSH_PORT（可空=22）", "TERMINAL_SSH_PORT (empty=22)"), L("22", "22"), "text"),
    ],
  },
  {
    id: "singularity",
    name: L("Singularity/Apptainer", "Singularity/Apptainer"),
    defaultHint: L("TERMINAL_SINGULARITY_IMAGE 等", "TERMINAL_SINGULARITY_IMAGE, …"),
    configFields: [
      F(
        "TERMINAL_SINGULARITY_IMAGE",
        L("TERMINAL_SINGULARITY_IMAGE", "TERMINAL_SINGULARITY_IMAGE"),
        L("例：docker://…", "e.g. docker://…"),
        "text"
      ),
    ],
  },
];

export const CATALOG_GATEWAY: SetupCatalogOption[] = [
  {
    id: "feishu",
    name: L("飞书", "飞书"),
    defaultHint: L("扫码一键创建并绑定", "Scan to create & bind"),
    configUi: "feishu_route_c",
  },
  {
    id: "qq",
    name: L("QQ", "QQ"),
    defaultHint: L("扫码绑定机器人", "Scan to bind bot"),
    configUi: "qqbot_route_c",
  },
  {
    id: "weixin",
    name: L("微信", "微信"),
    defaultHint: L("本机路线 C：扫码登录", "Route C: QR login in this app"),
    configUi: "weixin_route_c",
  },
  {
    id: "wecom",
    name: L("企微", "企微"),
    defaultHint: L("扫码创建或手动填写", "Scan to create or enter manually"),
    configUi: "wecom_route_c",
  },
];

export const CATALOG_TOOLS: SetupCatalogOption[] = [
  {
    id: "unified",
    name: L("统一 tools 流程", "Unified `hermes tools` flow"),
    defaultHint: L("按 CLI 分步填各厂商 Key", "Per-provider keys like CLI"),
    isDefault: true,
    configFields: [
      F("FIRECRAWL_API_KEY", L("FIRECRAWL_API_KEY（可空）", "FIRECRAWL_API_KEY (optional)"), L("选填", "optional"), "password"),
      F("BROWSERBASE_API_KEY", L("BROWSERBASE_API_KEY（可空）", "BROWSERBASE_API_KEY (optional)"), L("选填", "optional"), "password"),
    ],
  },
  { id: "toolset_default", name: L("toolsets 含 hermes-cli", "toolsets incl. hermes-cli"), defaultHint: L("默认", "default") },
  { id: "nous", name: L("Nous 托管能力", "Nous managed"), defaultHint: L("随订阅", "subscription") },
];

export const CATALOG_AGENT: SetupCatalogOption[] = [
  {
    id: "max_turns",
    name: L("max_turns / 迭代", "max_turns / iterations"),
    defaultHint: L("default：90", "default: 90"),
    configFields: [
      F("HERMES_MAX_ITERATIONS", L("HERMES_MAX_ITERATIONS", "HERMES_MAX_ITERATIONS"), L("如 90", "e.g. 90"), "text"),
    ],
  },
  {
    id: "tool_progress",
    name: L("display.tool_progress", "display.tool_progress"),
    defaultHint: L("default：all", "default: all"),
    configFields: [
      F(
        "display_tool_progress",
        L("工具进度：off / new / all / verbose", "off | new | all | verbose"),
        L("可空=不改", "empty = leave"),
        "text"
      ),
    ],
  },
  {
    id: "compression",
    name: L("compression.threshold", "compression.threshold"),
    defaultHint: L("0.50", "0.50"),
    configFields: [F("COMPRESSION_THRESHOLD", L("压缩阈值 0.5–0.95", "Compression threshold 0.5–0.95"), L("如 0.5", "e.g. 0.5"), "text")],
  },
  {
    id: "session_reset",
    name: L("session_reset", "session_reset"),
    defaultHint: L("mode both + idle 1440min + at_hour 4", "default bundle in config"),
  },
  {
    id: "reasoning",
    name: L("agent.reasoning_effort", "agent.reasoning_effort"),
    defaultHint: L("因模型而异", "model-specific"),
  },
  {
    id: "apply_defaults",
    name: L("推荐：与 Quick 相同的整包默认", "Recommended: same bundle as Quick defaults"),
    defaultHint: L("max_turns、tool_progress、compression、session_reset 等", "max_turns, tool progress, compression, session reset, …"),
    isDefault: true,
  },
];

export const CATALOG_BRAIN_CARDS: SetupCatalogOption[] = [
  {
    id: "starter",
    name: L("免费入门（DeepSeek 推荐）", "Free starter (DeepSeek—recommended)"),
    defaultHint: L("与推荐向导一致：DeepSeek 官方 API", "Same as the guided path: DeepSeek official API"),
    isDefault: true,
  },
  {
    id: "own",
    name: L("我有自己的API（OpenAI 兼容）", "My own API (OpenAI-compatible)"),
    defaultHint: L("在下一页填 Base URL + 模型 + API Key", "Base URL + model + key on next page"),
  },
];

export function getProviderRegistryOptions(): SetupCatalogOption[] {
  return PROVIDERS.map((p) => {
    const host = p.host.trim() ? p.host : "—";
    return {
      id: `reg_${p.id}`,
      name: L(p.label, p.label),
      defaultHint: L(`host: ${host}`, `host: ${host}`),
    };
  });
}

export const CATALOG_API_KEY: SetupCatalogOption[] = [
  {
    id: "main",
    name: L("本页主表单", "Main form on this page"),
    defaultHint: L("主模型 API Key 仅进系统凭据、不落 session", "Key goes to OS vault; not in session store"),
  },
  {
    id: "other_sections",
    name: L("其它 TTS 等", "Other TTS, …"),
    defaultHint: L("在对应向导页的「配置」里填（可全空）", "Use per-section “Configure” tables (all optional)"),
  },
];

export const CATALOG_BY_SECTION: Record<PostPassSectionId, SetupCatalogOption[]> = {
  tts: CATALOG_TTS,
  stt: CATALOG_STT,
  terminal: CATALOG_TERMINAL,
  gateway: CATALOG_GATEWAY,
  tools: CATALOG_TOOLS,
  agent: CATALOG_AGENT,
};
