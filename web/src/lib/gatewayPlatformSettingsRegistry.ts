// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

/**
 * Registry of gateway channel settings shown in Kabuqina Settings (not Wizard).
 * Keys must match Hermes `load_gateway_config` / gateway adapters.
 * i18n: `settings.channelEnv.*` in locales/strings.ts
 */

export type EnvFieldType = "string" | "secret" | "enum" | "bool";

export type EnvFieldDef = {
  envKey: string;
  labelKey: string;
  descriptionKey?: string;
  type: EnvFieldType;
  enumValues?: string[];
  placeholder?: string;
  recommended?: string;
  advanced?: boolean;
};

export type GatewayPlatformSection = {
  id: "connection" | "dm" | "groups" | "home" | "advanced";
  titleKey: string;
  fields: EnvFieldDef[];
  footnoteKey?: string;
};

export type GatewayPlatformRegistryEntry = {
  platform: string;
  sections: GatewayPlatformSection[];
};

export const HOST_ENV_PREFIXES: Record<string, string[]> = {
  qqbot: ["QQ_", "QQBOT_"],
  weixin: ["WEIXIN_"],
  dingtalk: ["DINGTALK_"],
  telegram: ["TELEGRAM_"],
  whatsapp: ["WHATSAPP_"],
  email: ["EMAIL_"],
};

const GW = "settings.channelEnv";

export const GATEWAY_PLATFORM_REGISTRY: GatewayPlatformRegistryEntry[] = [
  {
    platform: "qqbot",
    sections: [
      {
        id: "dm",
        titleKey: `${GW}.sectionDm`,
        fields: [
          {
            envKey: "QQ_ALLOW_ALL_USERS",
            labelKey: `${GW}.qqAllowAllDm`,
            descriptionKey: `${GW}.qqAllowAllDmDesc`,
            type: "bool",
            recommended: "false",
          },
          {
            envKey: "QQ_ALLOWED_USERS",
            labelKey: `${GW}.qqAllowedUsers`,
            descriptionKey: `${GW}.qqAllowedUsersDesc`,
            type: "string",
          },
        ],
      },
      {
        id: "groups",
        titleKey: `${GW}.sectionGroups`,
        fields: [
          {
            envKey: "QQ_GROUP_POLICY",
            labelKey: `${GW}.qqGroupPolicy`,
            descriptionKey: `${GW}.qqGroupPolicyDesc`,
            type: "enum",
            enumValues: ["open", "allowlist", "disabled"],
            recommended: "open",
          },
          {
            envKey: "QQ_GROUP_ALLOWED_USERS",
            labelKey: `${GW}.qqGroupAllowlist`,
            descriptionKey: `${GW}.qqGroupAllowlistDesc`,
            type: "string",
          },
        ],
      },
      {
        id: "home",
        titleKey: `${GW}.sectionHome`,
        fields: [
          {
            envKey: "QQBOT_HOME_CHANNEL",
            labelKey: `${GW}.qqHome`,
            descriptionKey: `${GW}.qqHomeDesc`,
            type: "string",
          },
        ],
      },
      {
        id: "advanced",
        titleKey: `${GW}.sectionAdvanced`,
        fields: [
          {
            envKey: "QQ_MARKDOWN_SUPPORT",
            labelKey: `${GW}.qqMarkdown`,
            type: "bool",
            advanced: true,
          },
          {
            envKey: "QQ_SANDBOX",
            labelKey: `${GW}.qqSandbox`,
            type: "bool",
            advanced: true,
          },
        ],
      },
    ],
  },
  {
    platform: "weixin",
    sections: [
      {
        id: "dm",
        titleKey: `${GW}.sectionDm`,
        fields: [
          {
            envKey: "WEIXIN_DM_POLICY",
            labelKey: `${GW}.wxDmPolicy`,
            descriptionKey: `${GW}.wxDmPolicyDesc`,
            type: "enum",
            enumValues: ["pairing", "open", "allowlist", "disabled"],
            recommended: "pairing",
          },
          {
            envKey: "WEIXIN_ALLOWED_USERS",
            labelKey: `${GW}.wxAllowedUsers`,
            descriptionKey: `${GW}.wxAllowedUsersDesc`,
            type: "string",
          },
        ],
      },
      {
        id: "groups",
        titleKey: `${GW}.sectionGroups`,
        fields: [
          {
            envKey: "WEIXIN_GROUP_POLICY",
            labelKey: `${GW}.wxGroupPolicy`,
            descriptionKey: `${GW}.wxGroupPolicyDesc`,
            type: "enum",
            enumValues: ["disabled", "open", "allowlist"],
            recommended: "disabled",
          },
          {
            envKey: "WEIXIN_GROUP_ALLOWED_USERS",
            labelKey: `${GW}.wxGroupAllowed`,
            type: "string",
          },
        ],
      },
      {
        id: "home",
        titleKey: `${GW}.sectionHome`,
        fields: [
          {
            envKey: "WEIXIN_HOME_CHANNEL",
            labelKey: `${GW}.wxHome`,
            type: "string",
          },
          {
            envKey: "WEIXIN_CDN_BASE_URL",
            labelKey: `${GW}.wxCdnUrl`,
            type: "string",
            advanced: true,
          },
        ],
      },
    ],
  },
  {
    platform: "dingtalk",
    sections: [
      {
        id: "dm",
        titleKey: `${GW}.sectionDm`,
        fields: [
          {
            envKey: "DINGTALK_ALLOW_ALL_USERS",
            labelKey: `${GW}.dingAllowAll`,
            descriptionKey: `${GW}.dingAllowAllDesc`,
            type: "bool",
            recommended: "true",
          },
          {
            envKey: "DINGTALK_ALLOWED_USERS",
            labelKey: `${GW}.dingAllowedUsers`,
            type: "string",
            advanced: true,
          },
        ],
      },
      {
        id: "home",
        titleKey: `${GW}.sectionHome`,
        fields: [
          {
            envKey: "DINGTALK_HOME_CHANNEL",
            labelKey: `${GW}.dingHome`,
            type: "string",
          },
        ],
      },
    ],
  },
  {
    platform: "email",
    sections: [
      {
        id: "connection",
        titleKey: `${GW}.sectionConnection`,
        fields: [
          {
            envKey: "EMAIL_AUTH_MODE",
            labelKey: `${GW}.emailAuthMode`,
            descriptionKey: `${GW}.emailAuthModeDesc`,
            type: "enum",
            enumValues: ["password", "oauth2"],
            recommended: "password",
          },
          {
            envKey: "EMAIL_OAUTH2_ACCESS_TOKEN",
            labelKey: `${GW}.emailOauth2AccessToken`,
            descriptionKey: `${GW}.emailOauth2AccessTokenDesc`,
            type: "secret",
            advanced: true,
          },
          {
            envKey: "EMAIL_OAUTH2_CLIENT_ID",
            labelKey: `${GW}.emailOauth2ClientId`,
            type: "string",
            advanced: true,
          },
          {
            envKey: "EMAIL_OAUTH2_REFRESH_TOKEN",
            labelKey: `${GW}.emailOauth2RefreshToken`,
            type: "secret",
            advanced: true,
          },
          {
            envKey: "EMAIL_OAUTH2_CLIENT_SECRET",
            labelKey: `${GW}.emailOauth2ClientSecret`,
            type: "secret",
            advanced: true,
          },
          {
            envKey: "EMAIL_OAUTH2_TENANT",
            labelKey: `${GW}.emailOauth2Tenant`,
            descriptionKey: `${GW}.emailOauth2TenantDesc`,
            type: "string",
            advanced: true,
          },
          {
            envKey: "EMAIL_OAUTH2_TOKEN_URL",
            labelKey: `${GW}.emailOauth2TokenUrl`,
            type: "string",
            advanced: true,
          },
          {
            envKey: "EMAIL_OAUTH2_SCOPE",
            labelKey: `${GW}.emailOauth2Scope`,
            type: "string",
            advanced: true,
          },
        ],
      },
      {
        id: "dm",
        titleKey: `${GW}.sectionDm`,
        fields: [
          {
            envKey: "EMAIL_ALLOWED_USERS",
            labelKey: `${GW}.emailAllowedSenders`,
            type: "string",
          },
        ],
      },
      {
        id: "home",
        titleKey: `${GW}.sectionHome`,
        fields: [
          {
            envKey: "EMAIL_HOME_ADDRESS",
            labelKey: `${GW}.emailHomeAddress`,
            type: "string",
            advanced: true,
          },
        ],
      },
    ],
  },
];

export function registryForPlatform(
  platform: string,
): GatewayPlatformRegistryEntry | undefined {
  return GATEWAY_PLATFORM_REGISTRY.find((e) => e.platform === platform);
}

export function allEnvKeysForPlatform(platform: string): string[] {
  const entry = registryForPlatform(platform);
  if (!entry) return [];
  const keys: string[] = [];
  for (const s of entry.sections) {
    for (const f of s.fields) keys.push(f.envKey);
  }
  return keys;
}
