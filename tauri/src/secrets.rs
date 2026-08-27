// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! API key storage backed by Windows Credential Manager (DPAPI).
//!
//! We use the cross-platform `keyring` crate directly. On Windows this
//! resolves to the native Credential Manager (DPAPI-encrypted at rest,
//! per-user). The plaintext key never touches a file we write; it lives
//! only in the OS vault and (transiently) in process memory.
//!
//! This module:
//!
//!   - Names the entry consistently (service = "Kabuqina", account = provider)
//!   - Persists which provider+host the user has chosen in settings.json
//!     (no secrets — just provider id and host)
//!   - Exposes commands the onboarding wizard calls
//!   - Hands the secret to the loopback bridge on demand

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::{AppHandle, Manager};

const SERVICE: &str = "Kabuqina";
const LEGACY_SERVICE: &str = "HermesDesk";

#[derive(Serialize, Deserialize, Clone, Debug, Default)]
pub struct ProviderConfig {
    pub provider: String, // "openrouter" | "openai" | "custom" | ...
    pub host: String,     // LLM API hostname for the network allowlist
    pub model: Option<String>,
    /// OpenAI-compatible chat/completions base URL (e.g. https://api.example.com/v1).
    #[serde(default)]
    pub api_base_url: Option<String>,
    /// Explicit Hermes wire protocol override. None means automatic detection.
    #[serde(default)]
    pub api_mode: Option<String>,
}

/// Independent multimodal provider configuration for Study capture.
///
/// The API key is stored under the Credential Manager account
/// `vision:<provider>` and is never allowed to fall back to the main LLM key.
#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq, Eq)]
pub struct VisionProviderConfig {
    pub provider: String,
    pub host: String,
    pub model: String,
    #[serde(default)]
    pub api_base_url: Option<String>,
}

const VENDOR_LLM_DISABLED: &str = "kabuqina.vendor_llm_disabled";
const LEGACY_VENDOR_LLM_DISABLED: &str = "hermesdesk.vendor_llm_disabled";

/// Build-time optional defaults so a distributor can ship a working demo key.
/// Set at **compile time** only (not committed to git):
/// `set KABUQINA_VENDOR_API_KEY=...&& set KABUQINA_VENDOR_BASE_URL=https://.../v1&& cargo tauri build`
fn vendor_api_key_compile() -> Option<&'static str> {
    option_env!("KABUQINA_VENDOR_API_KEY")
        .filter(|s| !s.is_empty())
        .or_else(|| option_env!("HERMESDESK_VENDOR_API_KEY").filter(|s| !s.is_empty()))
}

fn vendor_base_url_compile() -> Option<&'static str> {
    option_env!("KABUQINA_VENDOR_BASE_URL")
        .filter(|s| !s.is_empty())
        .or_else(|| option_env!("HERMESDESK_VENDOR_BASE_URL").filter(|s| !s.is_empty()))
}

fn vendor_model_compile() -> Option<&'static str> {
    option_env!("KABUQINA_VENDOR_MODEL")
        .filter(|s| !s.is_empty())
        .or_else(|| option_env!("HERMESDESK_VENDOR_MODEL").filter(|s| !s.is_empty()))
}

pub fn vendor_llm_available() -> bool {
    vendor_api_key_compile().is_some() && vendor_base_url_compile().is_some()
}

fn host_from_api_base(url: &str) -> String {
    if let Ok(parsed) = url::Url::parse(url.trim()) {
        if let Some(host) = parsed.host_str() {
            return host.to_string();
        }
    }
    let u = url.trim();
    let rest = u
        .strip_prefix("https://")
        .or_else(|| u.strip_prefix("http://"))
        .unwrap_or(u);
    rest.split('/').next().unwrap_or(rest).to_string()
}

fn normalize_api_mode(raw: Option<&str>) -> Result<Option<String>, String> {
    match raw.map(str::trim) {
        None => Ok(None),
        Some("chat_completions") => Ok(Some("chat_completions".into())),
        Some("anthropic_messages") => Ok(Some("anthropic_messages".into())),
        Some(_) => Err("api_mode must be chat_completions, anthropic_messages, or null".into()),
    }
}

fn validate_provider_config_for_save(cfg: &mut ProviderConfig, secret: &str) -> Result<(), String> {
    cfg.provider = cfg.provider.trim().to_ascii_lowercase();
    cfg.host = cfg.host.trim().to_ascii_lowercase();
    cfg.api_base_url = cfg
        .api_base_url
        .as_ref()
        .map(|s| s.trim().trim_end_matches('/').to_string())
        .filter(|s| !s.is_empty());
    cfg.api_mode = normalize_api_mode(cfg.api_mode.as_deref())?;

    if cfg.provider.is_empty() {
        return Err("provider must be set".into());
    }
    if secret.trim().is_empty() {
        return Err("secret must not be empty".into());
    }
    crate::validation::validate_env_value(secret)?;

    if cfg.provider == "custom" {
        let url = cfg
            .api_base_url
            .as_deref()
            .ok_or_else(|| "api_base_url is required for custom APIs".to_string())?;
        crate::validation::validate_public_endpoint(url, None)?;
        let base_host = host_from_api_base(url).to_ascii_lowercase();
        if cfg.host.is_empty() {
            cfg.host = base_host;
        } else if cfg.host != base_host {
            return Err("host must match api_base_url host".into());
        }
        return Ok(());
    }

    if cfg.host.is_empty() {
        return Err("host must be set".into());
    }
    crate::validation::validate_public_endpoint(&format!("https://{}/", cfg.host), None)?;

    if let Some(url) = cfg.api_base_url.as_deref() {
        crate::validation::validate_public_endpoint(url, None)?;
        let base_host = host_from_api_base(url).to_ascii_lowercase();
        if base_host != cfg.host {
            return Err("api_base_url host must match provider host".into());
        }
    }

    Ok(())
}

fn validate_vision_provider_name(provider: &str) -> Result<(), String> {
    let valid = !provider.is_empty()
        && provider.len() <= 64
        && provider
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.'));
    if valid {
        Ok(())
    } else {
        Err("vision provider is invalid".into())
    }
}

fn normalize_vision_config(
    cfg: &mut VisionProviderConfig,
    secret: Option<&str>,
) -> Result<(), String> {
    cfg.provider = cfg.provider.trim().to_ascii_lowercase();
    cfg.host = cfg.host.trim().to_ascii_lowercase();
    cfg.model = cfg.model.trim().to_string();
    cfg.api_base_url = cfg
        .api_base_url
        .as_ref()
        .map(|value| value.trim().trim_end_matches('/').to_string())
        .filter(|value| !value.is_empty());
    validate_vision_provider_name(&cfg.provider)?;
    if cfg.model.is_empty() || cfg.model.len() > 200 {
        return Err("vision model must be set and no longer than 200 characters".into());
    }

    let mut provider_cfg = ProviderConfig {
        provider: cfg.provider.clone(),
        host: cfg.host.clone(),
        model: Some(cfg.model.clone()),
        api_base_url: cfg.api_base_url.clone(),
        api_mode: None,
    };
    validate_provider_config_for_save(&mut provider_cfg, secret.unwrap_or("configured"))?;
    cfg.host = provider_cfg.host;
    cfg.api_base_url = provider_cfg.api_base_url;
    Ok(())
}

fn read_bool_setting(app: &AppHandle, key: &str) -> Option<bool> {
    let Some(f) = settings_file(app).ok() else {
        return None;
    };
    let Ok(raw) = std::fs::read_to_string(f) else {
        return None;
    };
    let Ok(v) = serde_json::from_str::<serde_json::Value>(&raw) else {
        return None;
    };
    bool_setting_value(&v, key)
}

fn bool_setting_value(v: &serde_json::Value, key: &str) -> Option<bool> {
    let value = v.get(key)?;
    value.as_bool().or_else(|| {
        value.as_str().map(|raw| {
            matches!(
                raw.trim().to_ascii_lowercase().as_str(),
                "1" | "true" | "yes"
            )
        })
    })
}

fn write_bool_setting(app: &AppHandle, key: &str, value: bool) -> Result<()> {
    let f = settings_file(app)?;
    let mut v: serde_json::Value = std::fs::read_to_string(&f)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    v[key] = serde_json::Value::Bool(value);
    std::fs::write(&f, serde_json::to_vec_pretty(&v)?)?;
    Ok(())
}

pub fn is_vendor_llm_disabled(app: &AppHandle) -> bool {
    if let Some(current) = read_bool_setting(app, VENDOR_LLM_DISABLED) {
        return current;
    }
    if let Some(legacy) = read_bool_setting(app, LEGACY_VENDOR_LLM_DISABLED) {
        let _ = write_bool_setting(app, VENDOR_LLM_DISABLED, legacy);
        return legacy;
    }
    false
}

/// Map a HermesDesk provider name to the env var that should hold its API key.
/// Mirrors ``_PROVIDER_ENV`` in ``python/src/secret_store.py``.
pub fn provider_api_key_env(provider: &str) -> String {
    match provider {
        "openrouter" => "OPENROUTER_API_KEY",
        "openai" => "OPENAI_API_KEY",
        "deepseek" => "DEEPSEEK_API_KEY",
        "custom" => "OPENAI_API_KEY",
        "anthropic" => "ANTHROPIC_API_KEY",
        "nous" => "NOUS_PORTAL_API_KEY",
        "groq" => "GROQ_API_KEY",
        "mistral" => "MISTRAL_API_KEY",
        "gemini" => "GOOGLE_API_KEY",
        "zai" => "GLM_API_KEY",
        "kimi-coding" => "KIMI_API_KEY",
        "kimi-coding-cn" => "KIMI_CN_API_KEY",
        "stepfun" => "STEPFUN_API_KEY",
        "minimax" => "MINIMAX_API_KEY",
        "minimax-cn" => "MINIMAX_CN_API_KEY",
        "alibaba" => "DASHSCOPE_API_KEY",
        "fireworks" => "FIREWORKS_API_KEY",
        "together" => "TOGETHER_API_KEY",
        "google" => "GOOGLE_API_KEY",
        "xai" => "XAI_API_KEY",
        "huggingface" => "HF_TOKEN",
        "arcee" => "ARCEEAI_API_KEY",
        _ => "OPENAI_API_KEY",
    }
    .to_string()
}

#[cfg(test)]
mod tests {
    use super::{
        bool_setting_value, clear_provider_secrets_with, clear_provider_state_with,
        credential_migration_message, keyring_service_candidates,
        normalize_credential_delete_result, normalize_vision_config, provider_api_key_env,
        read_and_migrate_provider_secret_with, select_provider_secret_with,
        validate_provider_config_for_save, vision_account, CopyForwardStatus, ProviderConfig,
        SecretOrigin, VisionProviderConfig, LEGACY_SERVICE, LEGACY_VENDOR_LLM_DISABLED, SERVICE,
        VENDOR_LLM_DISABLED,
    };

    fn custom_config(api_mode: Option<&str>) -> ProviderConfig {
        ProviderConfig {
            provider: "custom".into(),
            host: "api.example.com".into(),
            model: Some("model".into()),
            api_base_url: Some("https://api.example.com/anthropic".into()),
            api_mode: api_mode.map(str::to_string),
        }
    }

    #[test]
    fn old_provider_json_defaults_api_mode_to_automatic() {
        let cfg: ProviderConfig = serde_json::from_str(
            r#"{"provider":"custom","host":"api.example.com","model":"m","api_base_url":"https://api.example.com/v1"}"#,
        )
        .unwrap();

        assert_eq!(cfg.api_mode, None);
    }

    #[test]
    fn vendor_setting_preserves_explicit_false_on_new_key() {
        let settings = serde_json::json!({
            VENDOR_LLM_DISABLED: false,
            LEGACY_VENDOR_LLM_DISABLED: true,
        });

        assert_eq!(
            bool_setting_value(&settings, VENDOR_LLM_DISABLED),
            Some(false)
        );
        assert_eq!(
            bool_setting_value(&settings, LEGACY_VENDOR_LLM_DISABLED),
            Some(true)
        );
    }

    #[test]
    fn missing_vendor_setting_remains_distinct_from_false() {
        let settings = serde_json::json!({LEGACY_VENDOR_LLM_DISABLED: true});

        assert_eq!(bool_setting_value(&settings, VENDOR_LLM_DISABLED), None);
    }

    #[test]
    fn keyring_lookup_uses_current_service_before_legacy() {
        assert_eq!(keyring_service_candidates(), [SERVICE, LEGACY_SERVICE]);
    }

    #[test]
    fn keyring_selection_prefers_current_and_does_not_read_legacy() {
        let mut calls = Vec::new();
        let selected = select_provider_secret_with("openrouter", |service, provider| {
            calls.push((service.to_string(), provider.to_string()));
            Ok(Some("current-secret".to_string()))
        })
        .unwrap();

        assert_eq!(
            selected,
            Some(("current-secret".to_string(), SecretOrigin::Current))
        );
        assert_eq!(calls, vec![(SERVICE.to_string(), "openrouter".to_string())]);
    }

    #[test]
    fn keyring_selection_falls_back_only_on_explicit_miss() {
        let mut calls = Vec::new();
        let selected = select_provider_secret_with("anthropic", |service, provider| {
            calls.push((service.to_string(), provider.to_string()));
            if service == SERVICE {
                Ok(None)
            } else {
                Ok(Some("legacy-secret".to_string()))
            }
        })
        .unwrap();

        assert_eq!(
            selected,
            Some(("legacy-secret".to_string(), SecretOrigin::Legacy))
        );
        assert_eq!(
            calls,
            vec![
                (SERVICE.to_string(), "anthropic".to_string()),
                (LEGACY_SERVICE.to_string(), "anthropic".to_string()),
            ]
        );
    }

    #[test]
    fn keyring_selection_does_not_mask_current_read_failure() {
        let mut calls = Vec::new();
        let result = select_provider_secret_with("openrouter", |service, _provider| {
            calls.push(service.to_string());
            Err("backend unavailable".to_string())
        });

        assert_eq!(result, Err("backend unavailable".to_string()));
        assert_eq!(calls, vec![SERVICE.to_string()]);
    }

    #[test]
    fn keyring_legacy_secret_is_copied_forward_to_current_service() {
        let mut writes = Vec::new();
        let selected = read_and_migrate_provider_secret_with(
            "anthropic",
            |service, _provider| {
                if service == SERVICE {
                    Ok(None)
                } else {
                    Ok(Some("legacy-secret".to_string()))
                }
            },
            |service, provider, secret| {
                writes.push((
                    service.to_string(),
                    provider.to_string(),
                    secret.to_string(),
                ));
                Ok(())
            },
        )
        .unwrap();

        assert_eq!(
            selected,
            Some(("legacy-secret".to_string(), CopyForwardStatus::Copied))
        );
        assert_eq!(
            writes,
            vec![(
                SERVICE.to_string(),
                "anthropic".to_string(),
                "legacy-secret".to_string()
            )]
        );
    }

    #[test]
    fn keyring_copy_forward_failure_still_returns_legacy_secret() {
        let selected = read_and_migrate_provider_secret_with(
            "openrouter",
            |service, _provider| {
                if service == SERVICE {
                    Ok(None)
                } else {
                    Ok(Some("legacy-secret".to_string()))
                }
            },
            |_service, _provider, _secret| Err("backend unavailable".to_string()),
        )
        .unwrap();

        assert_eq!(
            selected,
            Some(("legacy-secret".to_string(), CopyForwardStatus::Failed))
        );
    }

    #[test]
    fn explicit_clear_attempts_current_and_legacy_services() {
        let mut calls = Vec::new();
        let result = clear_provider_secrets_with("openrouter", |service, provider| {
            calls.push((service.to_string(), provider.to_string()));
            if service == SERVICE {
                Err("canonical delete failed".to_string())
            } else {
                Ok(())
            }
        });

        assert_eq!(
            calls,
            vec![
                (SERVICE.to_string(), "openrouter".to_string()),
                (LEGACY_SERVICE.to_string(), "openrouter".to_string()),
            ]
        );
        assert!(result.unwrap_err().contains("canonical delete failed"));
    }

    #[test]
    fn missing_keyring_entry_is_a_successful_delete() {
        assert_eq!(
            normalize_credential_delete_result(Err(keyring::Error::NoEntry)),
            Ok(())
        );
    }

    #[test]
    fn explicit_clear_aggregates_both_delete_failures() {
        let error = clear_provider_secrets_with("openrouter", |service, _provider| {
            Err(format!("{service} backend unavailable"))
        })
        .unwrap_err();

        assert!(error.contains("Kabuqina: Kabuqina backend unavailable"));
        assert!(error.contains("HermesDesk: HermesDesk backend unavailable"));
    }

    #[test]
    fn explicit_clear_preserves_provider_config_when_a_delete_fails() {
        let mut config_cleared = false;
        let result = clear_provider_state_with(
            Some("openrouter"),
            |service, _provider| {
                if service == SERVICE {
                    Err("credential backend unavailable".to_string())
                } else {
                    Ok(())
                }
            },
            || {
                config_cleared = true;
                Ok(())
            },
        );

        assert!(result.is_err());
        assert!(!config_cleared);
    }

    #[test]
    fn keyring_migration_errors_and_logs_do_not_contain_secret() {
        let secret = "super-secret-marker";
        let selected = read_and_migrate_provider_secret_with(
            "openrouter",
            |service, _provider| {
                if service == SERVICE {
                    Ok(None)
                } else {
                    Ok(Some(secret.to_string()))
                }
            },
            |_service, _provider, copied_secret| {
                Err(format!("write failed while handling {copied_secret}"))
            },
        )
        .unwrap()
        .unwrap();

        assert_eq!(selected.0, secret);
        assert_eq!(selected.1, CopyForwardStatus::Failed);
        let message = credential_migration_message("openrouter", selected.1).unwrap();
        assert!(!message.contains(secret));
        assert!(!format!("{:?}", selected.1).contains(secret));
    }

    #[test]
    fn save_config_accepts_concrete_api_modes() {
        for mode in ["chat_completions", "anthropic_messages"] {
            let mut cfg = custom_config(Some(mode));
            validate_provider_config_for_save(&mut cfg, "sk-test").unwrap();
            assert_eq!(cfg.api_mode.as_deref(), Some(mode));
        }
    }

    #[test]
    fn save_config_rejects_auto_and_unknown_api_modes() {
        for mode in ["auto", "anthropic", ""] {
            let mut cfg = custom_config(Some(mode));
            assert!(validate_provider_config_for_save(&mut cfg, "sk-test").is_err());
        }
    }

    #[test]
    fn provider_api_key_env_covers_native_hermes_providers() {
        assert_eq!(provider_api_key_env("openai"), "OPENAI_API_KEY");
        assert_eq!(provider_api_key_env("deepseek"), "DEEPSEEK_API_KEY");
        assert_eq!(provider_api_key_env("alibaba"), "DASHSCOPE_API_KEY");
        assert_eq!(provider_api_key_env("zai"), "GLM_API_KEY");
        assert_eq!(provider_api_key_env("kimi-coding"), "KIMI_API_KEY");
        assert_eq!(provider_api_key_env("kimi-coding-cn"), "KIMI_CN_API_KEY");
        assert_eq!(provider_api_key_env("minimax"), "MINIMAX_API_KEY");
        assert_eq!(provider_api_key_env("minimax-cn"), "MINIMAX_CN_API_KEY");
    }

    #[test]
    fn save_config_rejects_custom_loopback_base_url() {
        let mut cfg = ProviderConfig {
            provider: "custom".into(),
            host: "127.0.0.1".into(),
            model: None,
            api_base_url: Some("http://127.0.0.1:11434/v1".into()),
            api_mode: None,
        };

        let result = validate_provider_config_for_save(&mut cfg, "sk-test");

        assert!(result.is_err());
    }

    #[test]
    fn save_config_rejects_secret_with_control_chars() {
        let mut cfg = ProviderConfig {
            provider: "openrouter".into(),
            host: "openrouter.ai".into(),
            model: None,
            api_base_url: None,
            api_mode: None,
        };

        let result = validate_provider_config_for_save(&mut cfg, "sk-test\nEVIL=1");

        assert!(result.is_err());
    }

    #[test]
    fn save_config_derives_custom_host_from_valid_base_url() {
        let mut cfg = ProviderConfig {
            provider: "custom".into(),
            host: "".into(),
            model: None,
            api_base_url: Some("https://api.example.com/v1".into()),
            api_mode: None,
        };

        validate_provider_config_for_save(&mut cfg, "sk-test").unwrap();

        assert_eq!(cfg.host, "api.example.com");
    }

    #[test]
    fn endpoint_validation_allows_switching_provider_host() {
        // Regression: previously the validator pinned to the saved custom base,
        // so switching back to a recommended provider (e.g. DeepSeek) was rejected
        // with "does not match your configured API base". With no saved-base pin,
        // any public HTTPS host the user configures validates on its own merits.
        assert!(crate::validation::validate_public_endpoint(
            "https://api.deepseek.com/v1/models",
            None,
        )
        .is_ok());
    }

    #[test]
    fn vision_config_is_normalized_and_uses_separate_account() {
        let mut cfg = VisionProviderConfig {
            provider: " Alibaba ".into(),
            host: " DashScope.AliYunCS.com ".into(),
            model: " qwen-vl-max ".into(),
            api_base_url: Some("https://dashscope.aliyuncs.com/compatible-mode/v1/".into()),
        };
        normalize_vision_config(&mut cfg, Some("vision-secret")).unwrap();
        assert_eq!(cfg.provider, "alibaba");
        assert_eq!(cfg.host, "dashscope.aliyuncs.com");
        assert_eq!(cfg.model, "qwen-vl-max");
        assert_eq!(vision_account(&cfg.provider).unwrap(), "vision:alibaba");
        assert_ne!(vision_account(&cfg.provider).unwrap(), cfg.provider);
    }

    #[test]
    fn vision_config_rejects_loopback_control_chars_and_missing_model() {
        let mut loopback = VisionProviderConfig {
            provider: "custom".into(),
            host: "127.0.0.1".into(),
            model: "vision".into(),
            api_base_url: Some("http://127.0.0.1:11434/v1".into()),
        };
        assert!(normalize_vision_config(&mut loopback, Some("secret")).is_err());

        let mut injected = VisionProviderConfig {
            provider: "openai".into(),
            host: "api.openai.com".into(),
            model: "gpt-4o".into(),
            api_base_url: Some("https://api.openai.com/v1".into()),
        };
        assert!(normalize_vision_config(&mut injected, Some("secret\nEVIL=1")).is_err());
        injected.model.clear();
        assert!(normalize_vision_config(&mut injected, None).is_err());
    }
}

/// Keyring entry only (bridge may still fall back to compile-time vendor key).
pub fn read_user_secret(app: &AppHandle) -> Option<String> {
    let cfg = read_provider_cfg(app)?;
    read_provider_secret(&cfg.provider)
}

/// Resolved LLM parameters for the Python child (provider allowlist + Hermes env).
pub struct LlmSpawnParams {
    pub provider: String,
    pub llm_host: String,
    pub api_base_url: Option<String>,
    pub api_mode: Option<String>,
    pub hermes_model: Option<String>,
    pub inference_provider: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct VisionSpawnParams {
    pub provider: String,
    pub vision_host: String,
    pub api_base_url: Option<String>,
    pub model: String,
    pub configured: bool,
}

pub fn resolve_vision_spawn_params(app: &AppHandle) -> VisionSpawnParams {
    let Some(cfg) = read_vision_provider_cfg(app) else {
        return VisionSpawnParams::default();
    };
    VisionSpawnParams {
        provider: cfg.provider,
        vision_host: cfg.host,
        api_base_url: cfg.api_base_url,
        model: cfg.model,
        configured: read_current_vision_secret(app).is_some(),
    }
}

pub fn resolve_llm_spawn_params(app: &AppHandle) -> LlmSpawnParams {
    let user_secret = read_user_secret(app);
    let cfg = read_provider_cfg(app);
    // Vendor defaults apply only on a pristine install (no saved provider row).
    // Once the user has gone through onboarding, an empty keyring means "signed out",
    // not "fall back to the vendor demo key".
    let vendor_ok = user_secret.is_none()
        && cfg.is_none()
        && vendor_llm_available()
        && !is_vendor_llm_disabled(app);

    if vendor_ok {
        let base = vendor_base_url_compile().unwrap();
        return LlmSpawnParams {
            provider: "custom".into(),
            llm_host: host_from_api_base(base),
            api_base_url: Some(base.to_string()),
            api_mode: None,
            hermes_model: vendor_model_compile().map(|s| s.to_string()),
            inference_provider: Some("custom".into()),
        };
    }

    if let Some(c) = cfg {
        let prov = c.provider.clone();
        let mut host = c.host.clone();
        let api = c.api_base_url.clone().filter(|s| !s.trim().is_empty());
        if host.is_empty() {
            if let Some(ref u) = api {
                host = host_from_api_base(u);
            }
        }
        if host.is_empty() {
            host = "openrouter.ai".into();
        }
        let inf = if prov == "custom" {
            Some("custom".into())
        } else {
            None
        };
        return LlmSpawnParams {
            provider: prov,
            llm_host: host,
            api_base_url: api,
            api_mode: c.api_mode.clone(),
            hermes_model: c.model.clone().filter(|s| !s.trim().is_empty()),
            inference_provider: inf,
        };
    }

    LlmSpawnParams {
        provider: "deepseek".into(),
        llm_host: "api.deepseek.com".into(),
        api_base_url: Some("https://api.deepseek.com/v1".into()),
        api_mode: None,
        hermes_model: Some("deepseek-v4-flash".into()),
        inference_provider: None,
    }
}

fn settings_file(app: &AppHandle) -> Result<PathBuf> {
    let dir = app.path().app_local_data_dir().context("local data dir")?;
    std::fs::create_dir_all(&dir)?;
    Ok(dir.join("settings.json"))
}

fn read_provider_cfg(app: &AppHandle) -> Option<ProviderConfig> {
    let f = settings_file(app).ok()?;
    let raw = std::fs::read_to_string(f).ok()?;
    let v: serde_json::Value = serde_json::from_str(&raw).ok()?;
    let p = v.get("provider")?;
    serde_json::from_value(p.clone()).ok()
}

fn write_provider_cfg(app: &AppHandle, cfg: &ProviderConfig) -> Result<()> {
    let f = settings_file(app)?;
    let mut v: serde_json::Value = std::fs::read_to_string(&f)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    v["provider"] = serde_json::to_value(cfg)?;
    std::fs::write(&f, serde_json::to_vec_pretty(&v)?)?;
    Ok(())
}

/// Remove the saved provider row so we never treat a keyless `settings.json` as "configured".
fn clear_provider_cfg(app: &AppHandle) -> Result<()> {
    let f = settings_file(app)?;
    let mut v: serde_json::Value = std::fs::read_to_string(&f)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    if let Some(obj) = v.as_object_mut() {
        obj.remove("provider");
    }
    std::fs::write(&f, serde_json::to_vec_pretty(&v)?)?;
    Ok(())
}

fn read_vision_provider_cfg(app: &AppHandle) -> Option<VisionProviderConfig> {
    let file = settings_file(app).ok()?;
    let raw = std::fs::read_to_string(file).ok()?;
    let value: serde_json::Value = serde_json::from_str(&raw).ok()?;
    serde_json::from_value(value.get("vision_provider")?.clone()).ok()
}

fn write_vision_provider_cfg(app: &AppHandle, cfg: &VisionProviderConfig) -> Result<()> {
    let file = settings_file(app)?;
    let mut value: serde_json::Value = std::fs::read_to_string(&file)
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_else(|| serde_json::json!({}));
    value["vision_provider"] = serde_json::to_value(cfg)?;
    std::fs::write(&file, serde_json::to_vec_pretty(&value)?)?;
    Ok(())
}

fn clear_vision_provider_cfg(app: &AppHandle) -> Result<()> {
    let file = settings_file(app)?;
    let mut value: serde_json::Value = std::fs::read_to_string(&file)
        .ok()
        .and_then(|raw| serde_json::from_str(&raw).ok())
        .unwrap_or_else(|| serde_json::json!({}));
    if let Some(object) = value.as_object_mut() {
        object.remove("vision_provider");
    }
    std::fs::write(&file, serde_json::to_vec_pretty(&value)?)?;
    Ok(())
}

fn keyring_service_candidates() -> [&'static str; 2] {
    [SERVICE, LEGACY_SERVICE]
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SecretOrigin {
    Current,
    Legacy,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CopyForwardStatus {
    NotNeeded,
    Copied,
    Failed,
}

/// Pure selection seam used by the keyring adapter and unit tests. A failed
/// current lookup is not treated as a miss: only an explicit missing entry may
/// fall back to the legacy service.
fn select_provider_secret_with<F>(
    provider: &str,
    mut read: F,
) -> Result<Option<(String, SecretOrigin)>, String>
where
    F: FnMut(&str, &str) -> Result<Option<String>, String>,
{
    if let Some(secret) = read(SERVICE, provider)? {
        return Ok(Some((secret, SecretOrigin::Current)));
    }
    if let Some(secret) = read(LEGACY_SERVICE, provider)? {
        return Ok(Some((secret, SecretOrigin::Legacy)));
    }
    Ok(None)
}

/// Read a credential and copy a legacy-only value into the canonical service.
/// Copy failures are reduced to a status so backend error strings can never
/// accidentally include the secret in a caller's log message.
fn read_and_migrate_provider_secret_with<R, W>(
    provider: &str,
    read: R,
    mut write: W,
) -> Result<Option<(String, CopyForwardStatus)>, String>
where
    R: FnMut(&str, &str) -> Result<Option<String>, String>,
    W: FnMut(&str, &str, &str) -> Result<(), String>,
{
    let Some((secret, origin)) = select_provider_secret_with(provider, read)? else {
        return Ok(None);
    };
    if origin == SecretOrigin::Current {
        return Ok(Some((secret, CopyForwardStatus::NotNeeded)));
    }

    let status = if write(SERVICE, provider, &secret).is_ok() {
        CopyForwardStatus::Copied
    } else {
        CopyForwardStatus::Failed
    };
    Ok(Some((secret, status)))
}

fn credential_migration_message(provider: &str, status: CopyForwardStatus) -> Option<String> {
    match status {
        CopyForwardStatus::NotNeeded => None,
        CopyForwardStatus::Copied => Some(format!(
            "migrated legacy credential for provider {provider}"
        )),
        CopyForwardStatus::Failed => Some(format!(
            "cannot migrate legacy credential for provider {provider}"
        )),
    }
}

/// Attempt both service deletions even if one backend operation fails, then
/// return all failures so the renderer cannot report a false success.
fn clear_provider_secrets_with<F>(provider: &str, mut delete: F) -> Result<(), String>
where
    F: FnMut(&str, &str) -> Result<(), String>,
{
    let mut failures = Vec::new();
    for service in keyring_service_candidates() {
        if let Err(err) = delete(service, provider) {
            failures.push(format!("{service}: {err}"));
        }
    }
    if failures.is_empty() {
        Ok(())
    } else {
        Err(format!(
            "failed to clear credentials for provider {provider}: {}",
            failures.join("; ")
        ))
    }
}

fn normalize_credential_delete_result(result: Result<(), keyring::Error>) -> Result<(), String> {
    match result {
        Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(err.to_string()),
    }
}

fn clear_provider_state_with<D, C>(
    provider: Option<&str>,
    delete: D,
    mut clear_config: C,
) -> Result<(), String>
where
    D: FnMut(&str, &str) -> Result<(), String>,
    C: FnMut() -> Result<(), String>,
{
    if let Some(provider) = provider {
        clear_provider_secrets_with(provider, delete)?;
    }
    clear_config()
}

fn entry_for_service(service: &str, provider: &str) -> Result<keyring::Entry, String> {
    keyring::Entry::new(service, provider).map_err(|e| e.to_string())
}

fn entry_for(provider: &str) -> Result<keyring::Entry, String> {
    entry_for_service(SERVICE, provider)
}

fn vision_account(provider: &str) -> Result<String, String> {
    validate_vision_provider_name(provider)?;
    Ok(format!("vision:{provider}"))
}

fn vision_entry(provider: &str) -> Result<keyring::Entry, String> {
    entry_for_service(SERVICE, &vision_account(provider)?)
}

pub fn read_current_vision_secret(app: &AppHandle) -> Option<String> {
    let cfg = read_vision_provider_cfg(app)?;
    match vision_entry(&cfg.provider).ok()?.get_password() {
        Ok(secret) if !secret.trim().is_empty() => Some(secret),
        Ok(_) | Err(keyring::Error::NoEntry) => None,
        Err(error) => {
            log::warn!(
                "cannot read vision credential for provider {}: {error}",
                cfg.provider
            );
            None
        }
    }
}

/// Read the canonical credential first. A legacy-only credential is copied to
/// the current service before being returned; failures never log the secret.
fn read_provider_secret(provider: &str) -> Option<String> {
    let selected = match read_and_migrate_provider_secret_with(
        provider,
        |service, provider| {
            let entry = entry_for_service(service, provider)?;
            match entry.get_password() {
                Ok(secret) => Ok(Some(secret)),
                Err(keyring::Error::NoEntry) => Ok(None),
                Err(err) => Err(err.to_string()),
            }
        },
        |service, provider, secret| {
            entry_for_service(service, provider)?
                .set_password(secret)
                .map_err(|err| err.to_string())
        },
    ) {
        Ok(selected) => selected,
        Err(err) => {
            log::warn!("cannot read credential for provider {provider}: {err}");
            return None;
        }
    };

    let (secret, status) = selected?;
    if let Some(message) = credential_migration_message(provider, status) {
        if status == CopyForwardStatus::Copied {
            log::info!("{message}");
        } else {
            log::warn!("{message}");
        }
    }
    Some(secret)
}

fn vendor_secret_fallback_enabled(app: &AppHandle) -> bool {
    read_provider_cfg(app).is_none() && vendor_llm_available() && !is_vendor_llm_disabled(app)
}

/// Secret handed to the Python child via the loopback bridge: user keyring
/// first, then optional compile-time vendor fallback on a pristine install only.
pub fn read_current_secret(app: &AppHandle) -> Option<String> {
    if let Some(s) = read_user_secret(app) {
        return Some(s);
    }
    if vendor_secret_fallback_enabled(app) {
        return vendor_api_key_compile().map(|s| s.to_string());
    }
    None
}

// --- IPC commands --------------------------------------------------------

/// Non-secret LLM row from `settings.json` plus whether a usable secret exists (keyring or vendor demo).
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LlmConfigPreview {
    pub has_secret: bool,
    pub provider: Option<String>,
    pub host: Option<String>,
    pub model: Option<String>,
    pub api_base_url: Option<String>,
    pub api_mode: Option<String>,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct VisionConfigPreview {
    pub has_secret: bool,
    pub provider: Option<String>,
    pub host: Option<String>,
    pub model: Option<String>,
    pub api_base_url: Option<String>,
}

#[tauri::command]
pub async fn cmd_vision_config_preview(app: AppHandle) -> Result<VisionConfigPreview, String> {
    let cfg = read_vision_provider_cfg(&app);
    Ok(VisionConfigPreview {
        has_secret: read_current_vision_secret(&app).is_some(),
        provider: cfg.as_ref().map(|value| value.provider.clone()),
        host: cfg.as_ref().map(|value| value.host.clone()),
        model: cfg.as_ref().map(|value| value.model.clone()),
        api_base_url: cfg.and_then(|value| value.api_base_url),
    })
}

#[tauri::command]
pub async fn cmd_save_vision_secret(
    app: AppHandle,
    mut cfg: VisionProviderConfig,
    secret: String,
) -> Result<(), String> {
    normalize_vision_config(&mut cfg, Some(&secret))?;
    vision_entry(&cfg.provider)?
        .set_password(secret.trim())
        .map_err(|error| error.to_string())?;
    write_vision_provider_cfg(&app, &cfg).map_err(|error| error.to_string())?;
    crate::schedule_embedded_hermes_respawn(app);
    Ok(())
}

#[tauri::command]
pub async fn cmd_update_vision_config(
    app: AppHandle,
    mut cfg: VisionProviderConfig,
    secret: Option<String>,
) -> Result<(), String> {
    normalize_vision_config(&mut cfg, secret.as_deref())?;
    if let Some(secret) = secret {
        vision_entry(&cfg.provider)?
            .set_password(secret.trim())
            .map_err(|error| error.to_string())?;
    }
    write_vision_provider_cfg(&app, &cfg).map_err(|error| error.to_string())?;
    crate::schedule_embedded_hermes_respawn(app);
    Ok(())
}

#[tauri::command]
pub async fn cmd_has_vision_secret(app: AppHandle) -> Result<bool, String> {
    Ok(read_current_vision_secret(&app).is_some())
}

#[tauri::command]
pub async fn cmd_clear_vision_secret(app: AppHandle) -> Result<(), String> {
    if let Some(cfg) = read_vision_provider_cfg(&app) {
        normalize_credential_delete_result(vision_entry(&cfg.provider)?.delete_credential())?;
    }
    clear_vision_provider_cfg(&app).map_err(|error| error.to_string())?;
    crate::schedule_embedded_hermes_respawn(app);
    Ok(())
}

#[tauri::command]
pub async fn cmd_llm_config_preview(app: AppHandle) -> Result<LlmConfigPreview, String> {
    let has_secret = read_current_secret(&app).is_some();
    let mut cfg = read_provider_cfg(&app);

    // Auto-migrate legacy config: provider=custom + deepseek base_url → provider=deepseek
    if let Some(ref mut c) = cfg {
        if c.provider == "custom"
            && c.api_base_url
                .as_deref()
                .unwrap_or("")
                .contains("deepseek.com")
        {
            c.provider = "deepseek".to_string();
            write_provider_cfg(&app, c).ok();
        }
    }

    Ok(LlmConfigPreview {
        has_secret,
        provider: cfg.as_ref().map(|c| c.provider.clone()),
        host: cfg
            .as_ref()
            .map(|c| c.host.clone())
            .filter(|s| !s.trim().is_empty()),
        model: cfg.as_ref().and_then(|c| c.model.clone()),
        api_base_url: cfg.as_ref().and_then(|c| c.api_base_url.clone()),
        api_mode: cfg.as_ref().and_then(|c| c.api_mode.clone()),
    })
}

#[tauri::command]
pub async fn cmd_save_secret(
    app: AppHandle,
    mut cfg: ProviderConfig,
    secret: String,
) -> Result<(), String> {
    validate_provider_config_for_save(&mut cfg, &secret)?;
    entry_for(&cfg.provider)?
        .set_password(&secret)
        .map_err(|e| e.to_string())?;
    write_provider_cfg(&app, &cfg).map_err(|e| e.to_string())?;
    let _ = write_bool_setting(&app, VENDOR_LLM_DISABLED, false);
    crate::schedule_embedded_hermes_respawn(app);
    Ok(())
}

#[tauri::command]
pub async fn cmd_update_llm_config(
    app: AppHandle,
    mut cfg: ProviderConfig,
    secret: Option<String>,
) -> Result<(), String> {
    cfg.provider = cfg.provider.trim().to_ascii_lowercase();
    cfg.host = cfg.host.trim().to_ascii_lowercase();
    cfg.api_base_url = cfg
        .api_base_url
        .as_ref()
        .map(|s| s.trim().trim_end_matches('/').to_string())
        .filter(|s| !s.is_empty());
    cfg.api_mode = normalize_api_mode(cfg.api_mode.as_deref())?;

    if cfg.provider.is_empty() {
        return Err("provider must be set".into());
    }

    if let Some(ref s) = secret {
        let trimmed = s.trim();
        if trimmed.is_empty() {
            return Err("secret must not be empty".into());
        }
        crate::validation::validate_env_value(trimmed)?;
        entry_for(&cfg.provider)?
            .set_password(trimmed)
            .map_err(|e| e.to_string())?;
    }

    if cfg.provider == "custom" {
        let url = cfg
            .api_base_url
            .as_deref()
            .ok_or_else(|| "api_base_url is required for custom APIs".to_string())?;
        crate::validation::validate_public_endpoint(url, None)?;
        let base_host = host_from_api_base(url).to_ascii_lowercase();
        if cfg.host.is_empty() {
            cfg.host = base_host;
        } else if cfg.host != base_host {
            return Err("host must match api_base_url host".into());
        }
    } else {
        if cfg.host.is_empty() {
            return Err("host must be set".into());
        }
        crate::validation::validate_public_endpoint(&format!("https://{}/", cfg.host), None)?;
        if let Some(ref url) = cfg.api_base_url {
            crate::validation::validate_public_endpoint(url, None)?;
            let base_host = host_from_api_base(url).to_ascii_lowercase();
            if base_host != cfg.host {
                return Err("api_base_url host must match provider host".into());
            }
        }
    }

    write_provider_cfg(&app, &cfg).map_err(|e| e.to_string())?;
    let _ = write_bool_setting(&app, VENDOR_LLM_DISABLED, false);
    crate::schedule_embedded_hermes_respawn(app);
    Ok(())
}

#[tauri::command]
pub async fn cmd_has_secret(app: AppHandle) -> Result<bool, String> {
    Ok(read_current_secret(&app).is_some())
}

#[tauri::command]
pub async fn cmd_clear_secret(app: AppHandle) -> Result<(), String> {
    let cfg = read_provider_cfg(&app);
    clear_provider_state_with(
        cfg.as_ref().map(|config| config.provider.as_str()),
        |service, provider| {
            let entry = entry_for_service(service, provider)?;
            normalize_credential_delete_result(entry.delete_credential())
        },
        || clear_provider_cfg(&app).map_err(|err| err.to_string()),
    )?;
    let _ = write_bool_setting(&app, VENDOR_LLM_DISABLED, true);
    crate::schedule_embedded_hermes_respawn(app);
    Ok(())
}

#[tauri::command]
pub async fn cmd_validate_endpoint(
    _app: AppHandle,
    url: String,
    api_key: String,
) -> Result<(), String> {
    log::info!("cmd_validate_endpoint called: url={}", url);

    // Validate the endpoint the user is configuring right now. We intentionally
    // do NOT pin to the previously saved provider host: the user may be switching
    // providers or editing their base URL in this very form (e.g. custom → back
    // to the recommended DeepSeek), and pinning to stale on-disk config blocked
    // that legitimate change. The api key is renderer-supplied in this same call,
    // so the host pin added no real protection anyway. HTTPS + public-address
    // checks below still apply.
    crate::validation::validate_public_endpoint(&url, None)?;

    let trimmed = api_key.trim();
    let is_anthropic = url.contains("api.anthropic.com");

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(15))
        .no_proxy()
        .build()
        .map_err(|e| format!("client build error: {}", e))?;

    let mut req = client.get(&url);
    if is_anthropic {
        req = req
            .header("x-api-key", trimmed)
            .header("anthropic-version", "2023-06-01");
    } else {
        req = req.header("Authorization", format!("Bearer {trimmed}"));
    }

    let res = req
        .send()
        .await
        .map_err(|e| format!("Couldn't reach that API address: {} (url={})", e, url))?;
    let status = res.status();
    log::info!("cmd_validate_endpoint response: status={}", status);
    if status == reqwest::StatusCode::UNAUTHORIZED || status == reqwest::StatusCode::FORBIDDEN {
        return Err("That pass didn't work. Double-check you copied the whole thing.".into());
    }
    if !status.is_success() && status != reqwest::StatusCode::BAD_REQUEST {
        return Err(format!(
            "That API address answered {}. Check the URL ends with /v1.",
            status
        ));
    }
    Ok(())
}
