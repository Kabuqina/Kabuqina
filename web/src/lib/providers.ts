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
    id: "openrouter",
    label: "OpenRouter",
    host: "openrouter.ai",
    signupUrl: "https://openrouter.ai/keys",
    validateUrl: "https://openrouter.ai/api/v1/auth/key",
    validateAuth: (k) => `Bearer ${k}`,
    keyPrefixHint: "sk-or-",
    blurb: "Optional: many models behind one key. Free tier—pick if you need multi-vendor routing.",
    freeTier: true,
  },
  {
    id: "openai",
    label: "OpenAI",
    host: "api.openai.com",
    signupUrl: "https://platform.openai.com/api-keys",
    validateUrl: "https://api.openai.com/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    keyPrefixHint: "sk-",
    blurb: "GPT-5.x and friends. Pay as you go.",
    freeTier: false,
  },
  {
    id: "anthropic",
    label: "Anthropic",
    host: "api.anthropic.com",
    signupUrl: "https://console.anthropic.com/settings/keys",
    validateUrl: "https://api.anthropic.com/v1/models",
    validateAuth: (k) => k,
    keyPrefixHint: "sk-ant-",
    blurb: "Claude. Excellent at writing and reasoning.",
    freeTier: false,
  },
  {
    id: "nous",
    label: "Nous Portal",
    host: "portal.nousresearch.com",
    signupUrl: "https://portal.nousresearch.com",
    validateUrl: "https://portal.nousresearch.com/api/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Nous Research's hosted Hermes models.",
    freeTier: false,
  },
  {
    id: "groq",
    label: "Groq",
    host: "api.groq.com",
    signupUrl: "https://console.groq.com/keys",
    validateUrl: "https://api.groq.com/openai/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    keyPrefixHint: "gsk_",
    blurb: "Very fast Llama / Mixtral. Free tier with rate limits.",
    freeTier: true,
  },
  {
    id: "mistral",
    label: "Mistral",
    host: "api.mistral.ai",
    signupUrl: "https://console.mistral.ai/api-keys",
    validateUrl: "https://api.mistral.ai/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Mistral's hosted models.",
    freeTier: false,
  },
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
    id: "gemini",
    label: "Google AI Studio",
    host: "generativelanguage.googleapis.com",
    signupUrl: "https://aistudio.google.com/app/apikey",
    validateUrl: "https://generativelanguage.googleapis.com/v1beta/openai/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Gemini models through Google AI Studio.",
    freeTier: true,
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
    id: "minimax",
    label: "MiniMax",
    host: "api.minimax.io",
    signupUrl: "https://platform.minimax.io/user-center/basic-information/interface-key",
    validateUrl: "https://api.minimax.io/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    skipEndpointValidation: true,
    blurb: "MiniMax global direct API.",
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
    id: "xai",
    label: "xAI",
    host: "api.x.ai",
    signupUrl: "https://console.x.ai/team/api-keys",
    validateUrl: "https://api.x.ai/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Grok models through xAI.",
    freeTier: false,
  },
  {
    id: "nvidia",
    label: "NVIDIA NIM",
    host: "integrate.api.nvidia.com",
    signupUrl: "https://build.nvidia.com/settings/api-keys",
    validateUrl: "https://integrate.api.nvidia.com/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "NVIDIA-hosted open models.",
    freeTier: false,
  },
  {
    id: "huggingface",
    label: "Hugging Face",
    host: "router.huggingface.co",
    signupUrl: "https://huggingface.co/settings/tokens",
    validateUrl: "https://router.huggingface.co/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Hugging Face inference providers.",
    freeTier: true,
  },
  {
    id: "arcee",
    label: "Arcee AI",
    host: "api.arcee.ai",
    signupUrl: "https://app.arcee.ai/settings/api-keys",
    validateUrl: "https://api.arcee.ai/api/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Arcee Trinity models.",
    freeTier: false,
  },
  {
    id: "gmi",
    label: "GMI Cloud",
    host: "api.gmi-serving.com",
    signupUrl: "https://console.gmicloud.ai/",
    validateUrl: "https://api.gmi-serving.com/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "GMI multi-model direct API.",
    freeTier: false,
  },
  {
    id: "ollama-cloud",
    label: "Ollama Cloud",
    host: "ollama.com",
    signupUrl: "https://ollama.com/settings/keys",
    validateUrl: "https://ollama.com/v1/models",
    validateAuth: (k) => `Bearer ${k}`,
    blurb: "Cloud-hosted Ollama models.",
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
