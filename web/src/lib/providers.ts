// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * The set of LLM providers Kabuqina's onboarding wizard knows about.
 * Each provider lists:
 *   - id            stable internal id matched in the Python overlay
 *   - host          the API host added to the network allowlist
 *   - signupUrl     where to send the user from "Get your access pass"
 *   - validateUrl   a cheap GET endpoint we ping with the pasted key
 *   - validateAuth  how to format the Authorization header for validation
 *   - keyPrefixHint a hint we show if the pasted key clearly looks wrong
 */
export type ProviderId =
  | "openrouter"
  | "openai"
  | "anthropic"
  | "deepseek"
  | "nous"
  | "groq"
  | "mistral"
  | "gemini"
  | "zai"
  | "kimi-coding"
  | "kimi-coding-cn"
  | "stepfun"
  | "minimax"
  | "minimax-cn"
  | "alibaba"
  | "xai"
  | "nvidia"
  | "huggingface"
  | "arcee"
  | "gmi"
  | "ollama-cloud"
  | "custom";

export interface Provider {
  id: ProviderId;
  label: string;
  host: string;
  signupUrl: string;
  validateUrl: string;
  validateAuth: (key: string) => string;
  keyPrefixHint?: string;
  skipEndpointValidation?: boolean;
  blurb: string;
  freeTier: boolean;
}

export const PROVIDERS: Provider[] = [
  {
    id: "deepseek",
    label: "DeepSeek",
    host: "api.deepseek.com",
    signupUrl: "https://platform.deepseek.com/api_keys",
    validateUrl: "https://api.deepseek.com/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    keyPrefixHint: "sk-",
    blurb: "DeepSeek V4. Leading performance, competitive pricing.",
    freeTier: false,
  },
  {
    id: "zai",
    label: "Z.AI / GLM",
    host: "api.z.ai",
    signupUrl: "https://bigmodel.cn/usercenter/proj-mgmt/apikeys",
    validateUrl: "https://api.z.ai/api/paas/v4/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "GLM models through Z.AI / Zhipu.",
    freeTier: false,
  },
  {
    id: "kimi-coding",
    label: "Kimi / Moonshot",
    host: "api.kimi.com",
    signupUrl: "https://platform.moonshot.ai/console/api-keys",
    validateUrl: "https://api.kimi.com/coding/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Kimi Coding Plan and Moonshot API.",
    freeTier: false,
  },
  {
    id: "kimi-coding-cn",
    label: "Kimi / Moonshot (China)",
    host: "api.kimi.com",
    signupUrl: "https://platform.moonshot.cn/console/api-keys",
    validateUrl: "https://api.kimi.com/coding/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Moonshot China direct API.",
    freeTier: false,
  },
  {
    id: "stepfun",
    label: "StepFun Step Plan",
    host: "api.stepfun.ai",
    signupUrl: "https://platform.stepfun.com/account-info",
    validateUrl: "https://api.stepfun.ai/step_plan/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Agent and coding models through Step Plan.",
    freeTier: false,
  },
  {
    id: "minimax-cn",
    label: "MiniMax (China)",
    host: "api.minimaxi.com",
    signupUrl: "https://platform.minimaxi.com/user-center/basic-information/interface-key",
    validateUrl: "https://api.minimaxi.com/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    skipEndpointValidation: true,
    blurb: "MiniMax China direct API.",
    freeTier: false,
  },
  {
    id: "alibaba",
    label: "Alibaba Cloud / DashScope (Qwen)",
    host: "dashscope-intl.aliyuncs.com",
    signupUrl: "https://bailian.console.aliyun.com/?tab=model#/api-key",
    validateUrl: "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "DashScope Coding with Qwen plus multi-provider models.",
    freeTier: false,
  },
  {
    id: "custom",
    label: "Your own API",
    host: "",
    signupUrl: "",
    validateUrl: "",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Any OpenAI-compatible endpoint you choose (base URL + access pass).",
    freeTier: false,
  },
];

export function findProvider(id: ProviderId): Provider {
  const p = PROVIDERS.find((x) => x.id === id);
  if (!p) throw new Error(`unknown provider ${id}`);
  return p;
}
