// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Explicit v0.4 gateway-data export and cleanup.
//!
//! This boundary is deliberately finite. It never walks or removes a directory:
//! every writable key and removable file is named below, and cleanup requires a
//! verified export produced by this module first.

use base64::Engine;
use serde::Serialize;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use tauri::AppHandle;

const CONTRACT_VERSION: &str = "kabuqina.legacy-channel-upgrade/v1";
const CLEANUP_CONFIRMATION: &str = "REMOVE_LEGACY_CHANNEL_DATA";
const EXPORT_DIR: &str = "legacy-channel-exports";
const MAX_EXPORT_FILE_BYTES: u64 = 16 * 1024 * 1024;
const MAX_EXPORT_TOTAL_BYTES: u64 = 64 * 1024 * 1024;

pub const REMOVED_PLATFORMS: &[&str] = &[
    "discord",
    "feishu",
    "wecom",
    "wecom_callback",
    "sms",
    "slack",
    "signal",
    "matrix",
    "mattermost",
    "bluebubbles",
    "homeassistant",
    "yuanbao",
    "webhook",
    "api_server",
    "irc",
    "teams",
];

// Exact user-configurable names accepted by the v0.4 gateway and bundled
// plugins. Constants which only happened to contain an upper-case platform
// name are intentionally absent.
pub const REMOVED_ENV_KEYS: &[&str] = &[
    "API_SERVER_CORS_ORIGINS",
    "API_SERVER_ENABLED",
    "API_SERVER_HOST",
    "API_SERVER_KEY",
    "API_SERVER_MODEL_NAME",
    "API_SERVER_PORT",
    "BLUEBUBBLES_ALLOW_ALL_USERS",
    "BLUEBUBBLES_ALLOWED_USERS",
    "BLUEBUBBLES_HOME_CHANNEL",
    "BLUEBUBBLES_HOME_CHANNEL_NAME",
    "BLUEBUBBLES_PASSWORD",
    "BLUEBUBBLES_SEND_READ_RECEIPTS",
    "BLUEBUBBLES_SERVER",
    "BLUEBUBBLES_SERVER_URL",
    "BLUEBUBBLES_WEBHOOK_HOST",
    "BLUEBUBBLES_WEBHOOK_PATH",
    "BLUEBUBBLES_WEBHOOK_PORT",
    "DISCORD_ALLOW_ALL_USERS",
    "DISCORD_ALLOW_BOTS",
    "DISCORD_ALLOWED_CHANNELS",
    "DISCORD_ALLOWED_ROLES",
    "DISCORD_ALLOWED_USERS",
    "DISCORD_ALLOW_MENTION_EVERYONE",
    "DISCORD_ALLOW_MENTION_REPLIED_USER",
    "DISCORD_ALLOW_MENTION_ROLES",
    "DISCORD_ALLOW_MENTION_USERS",
    "DISCORD_AUTO_THREAD",
    "DISCORD_BOT_TOKEN",
    "DISCORD_FREE_RESPONSE_CHANNELS",
    "DISCORD_HOME_CHANNEL",
    "DISCORD_HOME_CHANNEL_NAME",
    "DISCORD_IGNORE_NO_MENTION",
    "DISCORD_IGNORED_CHANNELS",
    "DISCORD_NO_THREAD_CHANNELS",
    "DISCORD_PROXY",
    "DISCORD_REACTIONS",
    "DISCORD_REPLY_TO_MODE",
    "DISCORD_REQUIRE_MENTION",
    "DISCORD_STRICT_MENTION",
    "DISCORD_TOKEN",
    "FEISHU_ALLOW_ALL_USERS",
    "FEISHU_ALLOWED_USERS",
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_BOT_NAME",
    "FEISHU_CONNECTION_MODE",
    "FEISHU_DOMAIN",
    "FEISHU_ENCRYPT_KEY",
    "FEISHU_GROUP_POLICY",
    "FEISHU_HOME_CHANNEL",
    "FEISHU_HOME_CHANNEL_NAME",
    "FEISHU_REACTIONS",
    "FEISHU_VERIFICATION_TOKEN",
    "FEISHU_WEBHOOK_HOST",
    "FEISHU_WEBHOOK_PATH",
    "FEISHU_WEBHOOK_PORT",
    "IRC_ALLOW_ALL_USERS",
    "IRC_ALLOWED_USERS",
    "IRC_CHANNEL",
    "IRC_CHANNELS",
    "IRC_NICK",
    "IRC_NICKNAME",
    "IRC_NICKSERV_PASSWORD",
    "IRC_PORT",
    "IRC_SERVER",
    "IRC_SERVER_PASSWORD",
    "IRC_USE_TLS",
    "HASS_TOKEN",
    "HASS_URL",
    "HOMEASSISTANT_HOME_CHANNEL",
    "HOMEASSISTANT_HOME_CHANNEL_NAME",
    "MATRIX_ACCESS_TOKEN",
    "MATRIX_ALLOW_ALL_USERS",
    "MATRIX_ALLOWED_USERS",
    "MATRIX_AUTO_THREAD",
    "MATRIX_DEVICE_ID",
    "MATRIX_DM_AUTO_THREAD",
    "MATRIX_DM_MENTION_THREADS",
    "MATRIX_ENCRYPTION",
    "MATRIX_FREE_RESPONSE_ROOMS",
    "MATRIX_HOME_CHANNEL",
    "MATRIX_HOME_CHANNEL_NAME",
    "MATRIX_HOME_ROOM",
    "MATRIX_HOME_ROOM_NAME",
    "MATRIX_HOMESERVER",
    "MATRIX_HOMESERVER_URL",
    "MATRIX_HS",
    "MATRIX_PASSWORD",
    "MATRIX_PROXY",
    "MATRIX_REACTIONS",
    "MATRIX_RECOVERY_KEY",
    "MATRIX_REQUIRE_MENTION",
    "MATRIX_USER_ID",
    "MATTERMOST_ALLOW_ALL_USERS",
    "MATTERMOST_ALLOWED_USERS",
    "MATTERMOST_BOT_TOKEN",
    "MATTERMOST_FREE_RESPONSE_CHANNELS",
    "MATTERMOST_HOME_CHANNEL",
    "MATTERMOST_HOME_CHANNEL_NAME",
    "MATTERMOST_REPLY_MODE",
    "MATTERMOST_REQUIRE_MENTION",
    "MATTERMOST_TEAM_ID",
    "MATTERMOST_TOKEN",
    "MATTERMOST_URL",
    "MSTEAMS_ALLOWED_USERS",
    "MSTEAMS_BOT_TOKEN",
    "SIGNAL_ACCOUNT",
    "SIGNAL_ALLOW_ALL_USERS",
    "SIGNAL_ALLOWED_USERS",
    "SIGNAL_GROUP_ALLOWED_USERS",
    "SIGNAL_HOME_CHANNEL",
    "SIGNAL_HOME_CHANNEL_NAME",
    "SIGNAL_HTTP_URL",
    "SIGNAL_IGNORE_STORIES",
    "SLACK_ALLOW_ALL_USERS",
    "SLACK_ALLOW_BOTS",
    "SLACK_ALLOWED_USERS",
    "SLACK_APP_TOKEN",
    "SLACK_BOT_TOKEN",
    "SLACK_FREE_RESPONSE_CHANNELS",
    "SLACK_HOME_CHANNEL",
    "SLACK_HOME_CHANNEL_NAME",
    "SLACK_REACTIONS",
    "SLACK_REQUIRE_MENTION",
    "SLACK_STRICT_MENTION",
    "SMS_ALLOW_ALL_USERS",
    "SMS_ALLOWED_USERS",
    "SMS_HOME_CHANNEL",
    "SMS_HOME_CHANNEL_NAME",
    "SMS_INSECURE_NO_SIGNATURE",
    "SMS_WEBHOOK_HOST",
    "SMS_WEBHOOK_PORT",
    "SMS_WEBHOOK_URL",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "TWILIO_PHONE_NUMBER",
    "TWILIO_PHONE_NUMBER_SID",
    "WEBHOOK_ENABLED",
    "WEBHOOK_HOST",
    "WEBHOOK_PATH",
    "WEBHOOK_PORT",
    "WEBHOOK_REPLAY_TOLERANCE_SECONDS",
    "WEBHOOK_SECRET",
    "WEBHOOK_URL",
    "WECOM_ALLOW_ALL_USERS",
    "WECOM_ALLOWED_USERS",
    "WECOM_BOT_ID",
    "WECOM_CALLBACK_AGENT_ID",
    "WECOM_CALLBACK_ALLOW_ALL_USERS",
    "WECOM_CALLBACK_ALLOWED_USERS",
    "WECOM_CALLBACK_CORP_ID",
    "WECOM_CALLBACK_CORP_SECRET",
    "WECOM_CALLBACK_ENCODING_AES_KEY",
    "WECOM_CALLBACK_HOME_CHANNEL",
    "WECOM_CALLBACK_HOME_CHANNEL_NAME",
    "WECOM_CALLBACK_HOST",
    "WECOM_CALLBACK_PORT",
    "WECOM_CALLBACK_TOKEN",
    "WECOM_DM_POLICY",
    "WECOM_GROUP_POLICY",
    "WECOM_HOME_CHANNEL",
    "WECOM_HOME_CHANNEL_NAME",
    "WECOM_SECRET",
    "WECOM_SETUP_METHOD",
    "WECOM_WEBSOCKET_URL",
    "YUANBAO_ALLOW_ALL_USERS",
    "YUANBAO_ALLOWED_USERS",
    "YUANBAO_API_DOMAIN",
    "YUANBAO_APP_ID",
    "YUANBAO_APP_KEY",
    "YUANBAO_APP_SECRET",
    "YUANBAO_BOT_ID",
    "YUANBAO_DM_ALLOW_FROM",
    "YUANBAO_DM_POLICY",
    "YUANBAO_GROUP_ALLOW_FROM",
    "YUANBAO_GROUP_POLICY",
    "YUANBAO_HOME_CHANNEL",
    "YUANBAO_HOME_CHANNEL_NAME",
    "YUANBAO_WS_URL",
    // Removed aliases on retained platforms. These are not valid new writes.
    "WEIXIN_APP_ID",
    "WEIXIN_APP_SECRET",
];

pub const QQ_LEGACY_HOME_KEYS: &[(&str, &str)] = &[
    ("QQ_HOME_CHANNEL", "QQBOT_HOME_CHANNEL"),
    ("QQ_HOME_CHANNEL_NAME", "QQBOT_HOME_CHANNEL_NAME"),
];

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyJobSummary {
    pub id: String,
    pub name: String,
    pub deliver: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyUpgradeInventory {
    pub contract_version: &'static str,
    pub source_home_path: String,
    pub canonical_home_present: bool,
    pub legacy_home_present: bool,
    pub removed_env_keys: Vec<String>,
    pub qq_legacy_home_keys: Vec<String>,
    pub exact_file_paths: Vec<String>,
    pub protected_directory_paths: Vec<String>,
    pub removed_config_platforms: Vec<String>,
    pub removed_channel_platforms: Vec<String>,
    pub removed_pairing_rate_limits: usize,
    pub legacy_jobs: Vec<LegacyJobSummary>,
    pub legacy_session_origins: usize,
    pub total_cleanup_items: usize,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyExportResult {
    pub contract_version: &'static str,
    pub export_id: String,
    pub path: String,
    pub exported_files: usize,
    pub skipped_oversize_files: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LegacyCleanupResult {
    pub contract_version: &'static str,
    pub removed_env_keys: usize,
    pub migrated_qq_home_keys: usize,
    pub removed_files: usize,
    pub removed_config_platforms: usize,
    pub removed_channel_platforms: usize,
    pub removed_pairing_rate_limits: usize,
    pub retained_legacy_jobs: usize,
    pub retained_legacy_session_origins: usize,
    pub remaining_cleanup_items: usize,
}

fn select_home(data_dir: &Path) -> PathBuf {
    let canonical = data_dir.join("kabuqina-home");
    let legacy = data_dir.join("hermes-home");
    if canonical.exists() || !legacy.exists() {
        canonical
    } else {
        legacy
    }
}

fn removed_set() -> BTreeSet<&'static str> {
    REMOVED_PLATFORMS.iter().copied().collect()
}

fn parse_dotenv(content: &str) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    for line in content.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            continue;
        }
        if let Some((key, value)) = trimmed.split_once('=') {
            out.insert(key.trim().to_ascii_uppercase(), value.to_string());
        }
    }
    out
}

fn patch_dotenv(content: &str) -> (String, usize, usize) {
    let removed: BTreeSet<&str> = REMOVED_ENV_KEYS.iter().copied().collect();
    let legacy_map: BTreeMap<&str, &str> = QQ_LEGACY_HOME_KEYS.iter().copied().collect();
    let existing = parse_dotenv(content);
    let mut output = Vec::new();
    let mut removed_count = 0;
    let mut migrated = 0;

    for line in content.lines() {
        let trimmed = line.trim();
        let key = trimmed
            .split_once('=')
            .map(|(raw, _)| raw.trim().to_ascii_uppercase());
        if let Some(key) = key {
            if removed.contains(key.as_str()) || legacy_map.contains_key(key.as_str()) {
                removed_count += 1;
                continue;
            }
        }
        output.push(line.to_string());
    }

    for (legacy, canonical) in QQ_LEGACY_HOME_KEYS {
        if !existing.contains_key(*canonical) {
            if let Some(value) = existing.get(*legacy) {
                output.push(format!("{canonical}={value}"));
                migrated += 1;
            }
        }
    }
    let mut rendered = output.join("\n");
    if !rendered.is_empty() {
        rendered.push('\n');
    }
    (rendered, removed_count, migrated)
}

fn yaml_platform_key(line: &str) -> Option<String> {
    if !line.starts_with("  ") || line.starts_with("   ") {
        return None;
    }
    let raw = line[2..].split_once(':')?.0.trim();
    Some(raw.trim_matches(['\'', '"']).to_ascii_lowercase())
}

fn strip_removed_yaml_platforms(content: &str) -> (String, usize) {
    let removed = removed_set();
    let mut in_platforms = false;
    let mut skipping = false;
    let mut removed_count = 0;
    let mut out = Vec::new();

    for line in content.lines() {
        let trimmed = line.trim();
        if !line.starts_with(char::is_whitespace)
            && !trimmed.is_empty()
            && !trimmed.starts_with('#')
        {
            in_platforms = trimmed == "platforms:";
            skipping = false;
        } else if in_platforms {
            if let Some(key) = yaml_platform_key(line) {
                skipping = removed.contains(key.as_str());
                if skipping {
                    removed_count += 1;
                }
            }
        }
        if !skipping {
            out.push(line.to_string());
        }
    }
    let mut rendered = out.join("\n");
    if !rendered.is_empty() {
        rendered.push('\n');
    }
    (rendered, removed_count)
}

fn removed_platforms_in_json(path: &Path) -> Vec<String> {
    let Ok(raw) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let Ok(value) = serde_json::from_str::<Value>(&raw) else {
        return Vec::new();
    };
    let mut found = BTreeSet::new();
    let removed = removed_set();
    if let Some(obj) = value.get("platforms").and_then(Value::as_object) {
        for key in obj.keys() {
            if removed.contains(key.to_ascii_lowercase().as_str()) {
                found.insert(key.to_ascii_lowercase());
            }
        }
    }
    if let Some(obj) = value.as_object() {
        for key in obj.keys() {
            if removed.contains(key.to_ascii_lowercase().as_str()) {
                found.insert(key.to_ascii_lowercase());
            }
        }
    }
    found.into_iter().collect()
}

fn remove_json_platforms(path: &Path) -> Result<usize, String> {
    if !path.exists() {
        return Ok(0);
    }
    let raw = std::fs::read_to_string(path).map_err(|e| format!("read {}: {e}", path.display()))?;
    let mut value: Value = serde_json::from_str(&raw)
        .map_err(|e| format!("refusing to rewrite malformed {}: {e}", path.display()))?;
    let removed = removed_set();
    let mut count = 0;
    if let Some(obj) = value.get_mut("platforms").and_then(Value::as_object_mut) {
        let keys: Vec<String> = obj
            .keys()
            .filter(|key| removed.contains(key.to_ascii_lowercase().as_str()))
            .cloned()
            .collect();
        count += keys.len();
        for key in keys {
            obj.remove(&key);
        }
    }
    if let Some(obj) = value.as_object_mut() {
        let keys: Vec<String> = obj
            .keys()
            .filter(|key| removed.contains(key.to_ascii_lowercase().as_str()))
            .cloned()
            .collect();
        count += keys.len();
        for key in keys {
            obj.remove(&key);
        }
    }
    if count > 0 {
        write_verified(
            path,
            &serde_json::to_vec_pretty(&value).map_err(|e| e.to_string())?,
        )?;
    }
    Ok(count)
}

fn exact_file_candidates(data_dir: &Path, home: &Path) -> Vec<PathBuf> {
    let mut paths = vec![
        home.join("feishu_seen_message_ids.json"),
        home.join("feishu_comment_rules.json"),
        home.join("feishu_comment_pairing.json"),
        data_dir.join("feishu_qr_progress.json"),
        data_dir.join("feishu_qr_result.json"),
        data_dir.join("wecom_qr_progress.json"),
        data_dir.join("wecom_qr_result.json"),
    ];
    for platform in REMOVED_PLATFORMS {
        paths.push(home.join(format!("{platform}_threads.json")));
        for pairing_root in [home.join("pairing"), home.join("platforms").join("pairing")] {
            paths.push(pairing_root.join(format!("{platform}-pending.json")));
            paths.push(pairing_root.join(format!("{platform}-approved.json")));
        }
        let profile = home.join("profiles").join(platform);
        for name in [
            ".env",
            "config.yaml",
            "_host_prefs.md",
            "gateway_state.json",
            "gateway.pid",
            "gateway.lock",
        ] {
            paths.push(profile.join(name));
        }
    }
    paths
}

fn protected_directory_candidates(home: &Path) -> Vec<PathBuf> {
    let mut paths = Vec::new();
    for platform in REMOVED_PLATFORMS {
        paths.push(home.join("profiles").join(platform));
    }
    paths.push(home.join("matrix_crypto"));
    paths
}

fn legacy_head(value: &str) -> bool {
    let head = value
        .trim()
        .split(':')
        .next()
        .unwrap_or("")
        .to_ascii_lowercase();
    !matches!(
        head.as_str(),
        "local"
            | "desktop"
            | "origin"
            | "weixin"
            | "qqbot"
            | "dingtalk"
            | "telegram"
            | "whatsapp"
            | "email"
    )
}

fn legacy_jobs(home: &Path) -> Vec<LegacyJobSummary> {
    let path = home.join("cron").join("jobs.json");
    let Ok(raw) = std::fs::read_to_string(path) else {
        return Vec::new();
    };
    let Ok(value) = serde_json::from_str::<Value>(&raw) else {
        return Vec::new();
    };
    value
        .get("jobs")
        .and_then(Value::as_array)
        .into_iter()
        .flatten()
        .filter_map(|job| {
            let deliver = job.get("deliver")?.as_str()?.to_string();
            let removed_origin = deliver
                .split(',')
                .any(|part| part.trim().eq_ignore_ascii_case("origin"))
                && job
                    .get("origin")
                    .and_then(|origin| origin.get("platform"))
                    .and_then(Value::as_str)
                    .is_some_and(legacy_head);
            if !deliver.split(',').any(legacy_head) && !removed_origin {
                return None;
            }
            Some(LegacyJobSummary {
                id: job
                    .get("id")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string(),
                name: job
                    .get("name")
                    .and_then(Value::as_str)
                    .unwrap_or("")
                    .to_string(),
                deliver,
            })
        })
        .collect()
}

fn count_legacy_session_origins(home: &Path) -> usize {
    let all_platforms = [
        "weixin",
        "qqbot",
        "dingtalk",
        "telegram",
        "whatsapp",
        "email",
        "discord",
        "feishu",
        "wecom",
        "wecom_callback",
        "sms",
        "slack",
        "signal",
        "matrix",
        "mattermost",
        "bluebubbles",
        "homeassistant",
        "yuanbao",
        "webhook",
        "api_server",
        "irc",
        "teams",
    ];
    let mut paths = vec![home.join("sessions").join("sessions.json")];
    paths.extend(all_platforms.iter().map(|p| {
        home.join("profiles")
            .join(p)
            .join("sessions")
            .join("sessions.json")
    }));
    let mut count = 0;
    for path in paths {
        let Ok(raw) = std::fs::read_to_string(path) else {
            continue;
        };
        let Ok(value) = serde_json::from_str::<Value>(&raw) else {
            continue;
        };
        if let Some(obj) = value.as_object() {
            for session in obj.values() {
                let platform = session
                    .get("origin")
                    .and_then(|o| o.get("platform"))
                    .and_then(Value::as_str)
                    .or_else(|| session.get("platform").and_then(Value::as_str));
                if platform.is_some_and(legacy_head) {
                    count += 1;
                }
            }
        }
    }
    count
}

fn inventory_for(data_dir: &Path) -> LegacyUpgradeInventory {
    let home = select_home(data_dir);
    let env_path = home.join(".env");
    let env = std::fs::read_to_string(&env_path).unwrap_or_default();
    let parsed = parse_dotenv(&env);
    let removed_env_keys: Vec<String> = REMOVED_ENV_KEYS
        .iter()
        .filter(|key| parsed.contains_key(**key))
        .map(|s| s.to_string())
        .collect();
    let qq_legacy_home_keys: Vec<String> = QQ_LEGACY_HOME_KEYS
        .iter()
        .filter(|(key, _)| parsed.contains_key(*key))
        .map(|(key, _)| key.to_string())
        .collect();
    let exact_file_paths: Vec<String> = exact_file_candidates(data_dir, &home)
        .into_iter()
        .filter(|p| p.is_file())
        .map(|p| p.display().to_string())
        .collect();
    let protected_directory_paths: Vec<String> = protected_directory_candidates(&home)
        .into_iter()
        .filter(|p| p.is_dir())
        .map(|p| p.display().to_string())
        .collect();

    let config_path = home.join("config.yaml");
    let config_raw = std::fs::read_to_string(&config_path).unwrap_or_default();
    let (_, _) = strip_removed_yaml_platforms(&config_raw);
    let mut removed_config_platforms = BTreeSet::new();
    let removed = removed_set();
    let mut in_platforms = false;
    for line in config_raw.lines() {
        let trimmed = line.trim();
        if !line.starts_with(char::is_whitespace)
            && !trimmed.is_empty()
            && !trimmed.starts_with('#')
        {
            in_platforms = trimmed == "platforms:";
        } else if in_platforms {
            if let Some(key) = yaml_platform_key(line) {
                if removed.contains(key.as_str()) {
                    removed_config_platforms.insert(key);
                }
            }
        }
    }
    removed_config_platforms.extend(removed_platforms_in_json(&home.join("gateway.json")));
    let removed_channel_platforms = removed_platforms_in_json(&home.join("channel_directory.json"));
    let removed_pairing_rate_limits = [
        home.join("pairing").join("_rate_limits.json"),
        home.join("platforms")
            .join("pairing")
            .join("_rate_limits.json"),
    ]
    .iter()
    .map(|path| count_pairing_rate_limits(path))
    .sum();
    let legacy_jobs = legacy_jobs(&home);
    let legacy_session_origins = count_legacy_session_origins(&home);
    let total_cleanup_items = removed_env_keys.len()
        + qq_legacy_home_keys.len()
        + exact_file_paths.len()
        + removed_config_platforms.len()
        + removed_channel_platforms.len()
        + removed_pairing_rate_limits;

    LegacyUpgradeInventory {
        contract_version: CONTRACT_VERSION,
        source_home_path: home.display().to_string(),
        canonical_home_present: data_dir.join("kabuqina-home").exists(),
        legacy_home_present: data_dir.join("hermes-home").exists(),
        removed_env_keys,
        qq_legacy_home_keys,
        exact_file_paths,
        protected_directory_paths,
        removed_config_platforms: removed_config_platforms.into_iter().collect(),
        removed_channel_platforms,
        removed_pairing_rate_limits,
        legacy_jobs,
        legacy_session_origins,
        total_cleanup_items,
    }
}

fn write_verified(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "target has no parent".to_string())?;
    std::fs::create_dir_all(parent).map_err(|e| format!("create {}: {e}", parent.display()))?;
    let temp = parent.join(format!(".c07-{}.tmp", uuid::Uuid::new_v4()));
    std::fs::write(&temp, bytes).map_err(|e| format!("write {}: {e}", temp.display()))?;
    let readback = std::fs::read(&temp).map_err(|e| format!("verify {}: {e}", temp.display()))?;
    if readback != bytes {
        let _ = std::fs::remove_file(&temp);
        return Err(format!("verification mismatch for {}", path.display()));
    }
    if !path.exists() {
        return std::fs::rename(&temp, path)
            .map_err(|e| format!("publish {}: {e}", path.display()));
    }

    // Windows rename does not replace an existing file. Move the verified old
    // value aside first and restore it if publishing the new value fails.
    let old = parent.join(format!(".c07-old-{}.tmp", uuid::Uuid::new_v4()));
    std::fs::rename(path, &old).map_err(|e| format!("stage {}: {e}", path.display()))?;
    if let Err(error) = std::fs::rename(&temp, path) {
        let _ = std::fs::rename(&old, path);
        let _ = std::fs::remove_file(&temp);
        return Err(format!("publish {}: {error}", path.display()));
    }
    std::fs::remove_file(&old).map_err(|e| format!("remove verified old {}: {e}", path.display()))
}

fn export_for(data_dir: &Path) -> Result<LegacyExportResult, String> {
    let inventory = inventory_for(data_dir);
    let home = PathBuf::from(&inventory.source_home_path);
    let mut candidates = exact_file_candidates(data_dir, &home);
    candidates.extend([
        home.join(".env"),
        home.join("config.yaml"),
        home.join("gateway.json"),
        home.join("channel_directory.json"),
        home.join("cron").join("jobs.json"),
        home.join("pairing").join("_rate_limits.json"),
        home.join("platforms")
            .join("pairing")
            .join("_rate_limits.json"),
    ]);
    let mut seen = BTreeSet::new();
    let mut files = Vec::new();
    let mut skipped = Vec::new();
    let mut total_bytes = 0_u64;
    for path in candidates {
        if !seen.insert(path.clone()) || !path.is_file() {
            continue;
        }
        let metadata = std::fs::symlink_metadata(&path)
            .map_err(|e| format!("inspect {}: {e}", path.display()))?;
        if metadata.file_type().is_symlink() {
            continue;
        }
        if metadata.len() > MAX_EXPORT_FILE_BYTES
            || total_bytes.saturating_add(metadata.len()) > MAX_EXPORT_TOTAL_BYTES
        {
            skipped.push(path.display().to_string());
            continue;
        }
        let bytes = std::fs::read(&path).map_err(|e| format!("export {}: {e}", path.display()))?;
        total_bytes += bytes.len() as u64;
        files.push(json!({
            "path": path.display().to_string(),
            "sha256": hex::encode(Sha256::digest(&bytes)),
            "data_base64": base64::engine::general_purpose::STANDARD.encode(bytes),
        }));
    }
    let exported_files = files.len();
    let payload = json!({
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "source_home_path": inventory.source_home_path,
        "inventory": inventory,
        "files": files,
        "skipped_oversize_files": skipped.clone(),
    });
    let bytes = serde_json::to_vec_pretty(&payload).map_err(|e| e.to_string())?;
    let export_id = hex::encode(Sha256::digest(&bytes));
    let path = data_dir.join(EXPORT_DIR).join(format!("{export_id}.json"));
    write_verified(&path, &bytes)?;
    let readback = std::fs::read(&path).map_err(|e| format!("verify export: {e}"))?;
    if hex::encode(Sha256::digest(&readback)) != export_id {
        return Err("legacy export hash verification failed".to_string());
    }
    Ok(LegacyExportResult {
        contract_version: CONTRACT_VERSION,
        export_id,
        path: path.display().to_string(),
        exported_files,
        skipped_oversize_files: skipped,
    })
}

fn verify_export(data_dir: &Path, export_id: &str) -> Result<(), String> {
    if export_id.len() != 64 || !export_id.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("invalid legacy export id".to_string());
    }
    let path = data_dir
        .join(EXPORT_DIR)
        .join(format!("{}.json", export_id.to_ascii_lowercase()));
    let bytes = std::fs::read(&path)
        .map_err(|_| "verified legacy export is required before cleanup".to_string())?;
    if hex::encode(Sha256::digest(&bytes)) != export_id.to_ascii_lowercase() {
        return Err("legacy export verification failed".to_string());
    }
    let payload: Value =
        serde_json::from_slice(&bytes).map_err(|_| "legacy export is malformed".to_string())?;
    if payload.get("contract_version").and_then(Value::as_str) != Some(CONTRACT_VERSION) {
        return Err("legacy export contract mismatch".to_string());
    }
    let expected_home = select_home(data_dir).display().to_string();
    if payload.get("source_home_path").and_then(Value::as_str) != Some(expected_home.as_str()) {
        return Err("legacy export belongs to a different home path".to_string());
    }
    if payload
        .get("skipped_oversize_files")
        .and_then(Value::as_array)
        .is_some_and(|files| !files.is_empty())
    {
        return Err("legacy export is incomplete; cleanup remains disabled".to_string());
    }
    Ok(())
}

fn clean_pairing_rate_limits(path: &Path) -> Result<usize, String> {
    if !path.exists() {
        return Ok(0);
    }
    let raw = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let mut value: Value = serde_json::from_str(&raw)
        .map_err(|e| format!("refusing to rewrite malformed {}: {e}", path.display()))?;
    let Some(obj) = value.as_object_mut() else {
        return Err(format!("{} is not an object", path.display()));
    };
    let removed = removed_set();
    let keys: Vec<String> = obj
        .keys()
        .filter(|key| {
            let normalized = key
                .strip_prefix("_lockout:")
                .or_else(|| key.strip_prefix("_failures:"))
                .unwrap_or(key);
            let platform = normalized
                .split(':')
                .next()
                .unwrap_or("")
                .to_ascii_lowercase();
            removed.contains(platform.as_str())
        })
        .cloned()
        .collect();
    for key in &keys {
        obj.remove(key);
    }
    if !keys.is_empty() {
        write_verified(
            path,
            &serde_json::to_vec_pretty(&value).map_err(|e| e.to_string())?,
        )?;
    }
    Ok(keys.len())
}

fn count_pairing_rate_limits(path: &Path) -> usize {
    let Ok(raw) = std::fs::read_to_string(path) else {
        return 0;
    };
    let Ok(value) = serde_json::from_str::<Value>(&raw) else {
        return 0;
    };
    let Some(obj) = value.as_object() else {
        return 0;
    };
    let removed = removed_set();
    obj.keys()
        .filter(|key| {
            let normalized = key
                .strip_prefix("_lockout:")
                .or_else(|| key.strip_prefix("_failures:"))
                .unwrap_or(key);
            let platform = normalized
                .split(':')
                .next()
                .unwrap_or("")
                .to_ascii_lowercase();
            removed.contains(platform.as_str())
        })
        .count()
}

fn preflight_json(path: &Path, require_object: bool) -> Result<(), String> {
    if !path.exists() {
        return Ok(());
    }
    let raw = std::fs::read_to_string(path)
        .map_err(|e| format!("refusing cleanup: cannot read {}: {e}", path.display()))?;
    let value: Value = serde_json::from_str(&raw)
        .map_err(|e| format!("refusing cleanup: malformed {}: {e}", path.display()))?;
    if require_object && !value.is_object() {
        return Err(format!(
            "refusing cleanup: {} is not an object",
            path.display()
        ));
    }
    Ok(())
}

fn preflight_cleanup(home: &Path) -> Result<(), String> {
    // Validate every structured rewrite before changing even the first file.
    preflight_json(&home.join("gateway.json"), true)?;
    preflight_json(&home.join("channel_directory.json"), true)?;
    preflight_json(&home.join("pairing").join("_rate_limits.json"), true)?;
    preflight_json(
        &home
            .join("platforms")
            .join("pairing")
            .join("_rate_limits.json"),
        true,
    )?;
    if home.join("config.yaml").exists() {
        std::fs::read_to_string(home.join("config.yaml"))
            .map_err(|e| format!("refusing cleanup: cannot read config.yaml: {e}"))?;
    }
    Ok(())
}

fn cleanup_for(
    data_dir: &Path,
    export_id: &str,
    confirmation: &str,
) -> Result<LegacyCleanupResult, String> {
    if confirmation != CLEANUP_CONFIRMATION {
        return Err("explicit legacy cleanup confirmation is required".to_string());
    }
    verify_export(data_dir, export_id)?;
    let before = inventory_for(data_dir);
    let home = PathBuf::from(&before.source_home_path);
    preflight_cleanup(&home)?;

    let env_path = home.join(".env");
    let (removed_env_keys, migrated_qq_home_keys) = if env_path.exists() {
        let raw = std::fs::read_to_string(&env_path).map_err(|e| e.to_string())?;
        let (patched, removed, migrated) = patch_dotenv(&raw);
        if patched != raw {
            write_verified(&env_path, patched.as_bytes())?;
        }
        (removed, migrated)
    } else {
        (0, 0)
    };

    let config_path = home.join("config.yaml");
    let mut removed_config_platforms = 0;
    if config_path.exists() {
        let raw = std::fs::read_to_string(&config_path).map_err(|e| e.to_string())?;
        let (patched, removed) = strip_removed_yaml_platforms(&raw);
        if patched != raw {
            write_verified(&config_path, patched.as_bytes())?;
        }
        removed_config_platforms += removed;
    }
    removed_config_platforms += remove_json_platforms(&home.join("gateway.json"))?;
    let removed_channel_platforms = remove_json_platforms(&home.join("channel_directory.json"))?;

    let mut removed_pairing_rate_limits = 0;
    for path in [
        home.join("pairing").join("_rate_limits.json"),
        home.join("platforms")
            .join("pairing")
            .join("_rate_limits.json"),
    ] {
        removed_pairing_rate_limits += clean_pairing_rate_limits(&path)?;
    }

    let mut removed_files = 0;
    for path in exact_file_candidates(data_dir, &home) {
        let Ok(metadata) = std::fs::symlink_metadata(&path) else {
            continue;
        };
        if metadata.file_type().is_file() && !metadata.file_type().is_symlink() {
            std::fs::remove_file(&path)
                .map_err(|e| format!("remove exact file {}: {e}", path.display()))?;
            removed_files += 1;
        }
    }
    let after = inventory_for(data_dir);
    Ok(LegacyCleanupResult {
        contract_version: CONTRACT_VERSION,
        removed_env_keys,
        migrated_qq_home_keys,
        removed_files,
        removed_config_platforms,
        removed_channel_platforms,
        removed_pairing_rate_limits,
        retained_legacy_jobs: after.legacy_jobs.len(),
        retained_legacy_session_origins: after.legacy_session_origins,
        remaining_cleanup_items: after.total_cleanup_items,
    })
}

#[tauri::command]
pub fn cmd_legacy_channel_inventory(app: AppHandle) -> Result<LegacyUpgradeInventory, String> {
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;
    Ok(inventory_for(&data_dir))
}

#[tauri::command]
pub fn cmd_legacy_channel_export(app: AppHandle) -> Result<LegacyExportResult, String> {
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;
    export_for(&data_dir)
}

#[tauri::command]
pub fn cmd_legacy_channel_cleanup(
    app: AppHandle,
    export_id: String,
    confirmation: String,
) -> Result<LegacyCleanupResult, String> {
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;
    cleanup_for(&data_dir, &export_id, &confirmation)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_data_dir(name: &str) -> PathBuf {
        std::env::temp_dir().join(format!("kabuqina-c07-{name}-{}", uuid::Uuid::new_v4()))
    }

    #[test]
    fn dotenv_cleanup_is_exact_and_qq_upgrade_is_explicit() {
        let raw = "TELEGRAM_BOT_TOKEN=keep\nDISCORD_BOT_TOKEN=drop\nDISCORD_CUSTOM_KEEP=keep\nQQ_HOME_CHANNEL=old-home\nQQBOT_HOME_CHANNEL_NAME=canonical\nQQ_HOME_CHANNEL_NAME=legacy-name\n";
        let (patched, removed, migrated) = patch_dotenv(raw);
        assert_eq!(removed, 3);
        assert_eq!(migrated, 1);
        assert!(patched.contains("TELEGRAM_BOT_TOKEN=keep"));
        assert!(patched.contains("DISCORD_CUSTOM_KEEP=keep"));
        assert!(patched.contains("QQBOT_HOME_CHANNEL=old-home"));
        assert!(patched.contains("QQBOT_HOME_CHANNEL_NAME=canonical"));
        assert!(!patched.contains("DISCORD_BOT_TOKEN="));
        assert!(!patched.contains("QQ_HOME_CHANNEL="));
    }

    #[test]
    fn yaml_cleanup_removes_only_exact_platform_sections() {
        let raw = "platforms:\n  discord:\n    enabled: true\n  telegram:\n    enabled: true\n  discord_archive:\n    enabled: true\nllm:\n  provider: keep\n";
        let (patched, removed) = strip_removed_yaml_platforms(raw);
        assert_eq!(removed, 1);
        assert!(!patched.contains("  discord:\n"));
        assert!(patched.contains("  telegram:\n"));
        assert!(patched.contains("  discord_archive:\n"));
        assert!(patched.contains("llm:\n  provider: keep"));
    }

    #[test]
    fn cleanup_requires_verified_export_and_never_removes_directories() {
        let data_dir = temp_data_dir("verified-export");
        let home = data_dir.join("kabuqina-home");
        std::fs::create_dir_all(home.join("profiles").join("discord").join("sessions")).unwrap();
        std::fs::write(
            home.join(".env"),
            "DISCORD_BOT_TOKEN=secret\nTELEGRAM_BOT_TOKEN=keep\n",
        )
        .unwrap();
        std::fs::write(
            home.join("profiles").join("discord").join(".env"),
            "DISCORD_BOT_TOKEN=secret\n",
        )
        .unwrap();
        std::fs::write(
            home.join("profiles")
                .join("discord")
                .join("sessions")
                .join("old.jsonl"),
            "history",
        )
        .unwrap();

        assert!(cleanup_for(&data_dir, "bad", CLEANUP_CONFIRMATION).is_err());
        let export = export_for(&data_dir).unwrap();
        let result = cleanup_for(&data_dir, &export.export_id, CLEANUP_CONFIRMATION).unwrap();
        assert_eq!(result.removed_files, 1);
        assert!(home.join("profiles").join("discord").is_dir());
        assert!(home
            .join("profiles")
            .join("discord")
            .join("sessions")
            .join("old.jsonl")
            .exists());
        assert_eq!(
            std::fs::read_to_string(home.join(".env")).unwrap(),
            "TELEGRAM_BOT_TOKEN=keep\n"
        );
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn legacy_jobs_and_sessions_are_inventory_only() {
        let data_dir = temp_data_dir("opaque-records");
        let home = data_dir.join("kabuqina-home");
        std::fs::create_dir_all(home.join("cron")).unwrap();
        std::fs::create_dir_all(home.join("sessions")).unwrap();
        std::fs::write(home.join("cron").join("jobs.json"), r#"{"jobs":[{"id":"old","name":"Old","deliver":"feishu:oc_1"},{"id":"new","deliver":"telegram:1"}]}"#).unwrap();
        std::fs::write(
            home.join("sessions").join("sessions.json"),
            r#"{"s":{"origin":{"platform":"retired_plugin","chat_id":"x"},"platform":"discord"}}"#,
        )
        .unwrap();
        let inventory = inventory_for(&data_dir);
        assert_eq!(inventory.legacy_jobs.len(), 1);
        assert_eq!(inventory.legacy_session_origins, 1);
        let export = export_for(&data_dir).unwrap();
        cleanup_for(&data_dir, &export.export_id, CLEANUP_CONFIRMATION).unwrap();
        assert!(home.join("cron").join("jobs.json").exists());
        assert!(home.join("sessions").join("sessions.json").exists());
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn pairing_cleanup_removes_only_removed_platform_keys() {
        let data_dir = temp_data_dir("pairing-rate-limit");
        let path = data_dir.join("_rate_limits.json");
        std::fs::create_dir_all(&data_dir).unwrap();
        std::fs::write(
            &path,
            r#"{"discord:u":1,"_lockout:wecom":2,"telegram:u":3}"#,
        )
        .unwrap();
        assert_eq!(clean_pairing_rate_limits(&path).unwrap(), 2);
        let value: Value = serde_json::from_str(&std::fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(value, json!({"telegram:u": 3}));
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn malformed_structured_record_fails_before_env_rewrite() {
        let data_dir = temp_data_dir("preflight");
        let home = data_dir.join("kabuqina-home");
        std::fs::create_dir_all(&home).unwrap();
        std::fs::write(home.join(".env"), "DISCORD_BOT_TOKEN=still-here\n").unwrap();
        std::fs::write(home.join("channel_directory.json"), "{broken").unwrap();
        let export = export_for(&data_dir).unwrap();

        let error = cleanup_for(&data_dir, &export.export_id, CLEANUP_CONFIRMATION).unwrap_err();

        assert!(error.contains("malformed"));
        assert_eq!(
            std::fs::read_to_string(home.join(".env")).unwrap(),
            "DISCORD_BOT_TOKEN=still-here\n"
        );
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn incomplete_export_cannot_authorize_cleanup() {
        let data_dir = temp_data_dir("oversize-export");
        let home = data_dir.join("kabuqina-home");
        let profile = home.join("profiles").join("discord");
        std::fs::create_dir_all(&profile).unwrap();
        std::fs::write(home.join(".env"), "DISCORD_BOT_TOKEN=still-here\n").unwrap();
        let oversized = std::fs::File::create(profile.join("config.yaml")).unwrap();
        oversized.set_len(MAX_EXPORT_FILE_BYTES + 1).unwrap();
        let export = export_for(&data_dir).unwrap();
        assert_eq!(export.skipped_oversize_files.len(), 1);

        let error = cleanup_for(&data_dir, &export.export_id, CLEANUP_CONFIRMATION).unwrap_err();

        assert!(error.contains("incomplete"));
        assert!(home.join(".env").exists());
        assert!(profile.join("config.yaml").exists());
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn v04_fixture_upgrades_without_reroute_or_recursive_delete() {
        let fixture: Value =
            serde_json::from_str(include_str!("../tests/fixtures/c07-v04-gateway-home.json"))
                .unwrap();
        let data_dir = temp_data_dir("v04-fixture");
        let home = data_dir.join("kabuqina-home");
        for (relative, content) in fixture["files"].as_object().unwrap() {
            let path = home.join(relative);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, content.as_str().unwrap()).unwrap();
        }

        let before = inventory_for(&data_dir);
        assert_eq!(before.legacy_jobs.len(), 1);
        assert_eq!(before.legacy_session_origins, 1);
        assert!(before
            .removed_env_keys
            .contains(&"FEISHU_APP_ID".to_string()));
        let export = export_for(&data_dir).unwrap();
        cleanup_for(&data_dir, &export.export_id, CLEANUP_CONFIRMATION).unwrap();

        let env = std::fs::read_to_string(home.join(".env")).unwrap();
        assert!(!env.contains("FEISHU_"));
        assert!(env.contains("QQBOT_HOME_CHANNEL=qq-old-home"));
        assert!(env.contains("TELEGRAM_BOT_TOKEN=telegram-keep"));
        let config = std::fs::read_to_string(home.join("config.yaml")).unwrap();
        assert!(!config.contains("  feishu:"));
        assert!(config.contains("  weixin:"));
        let gateway: Value =
            serde_json::from_str(&std::fs::read_to_string(home.join("gateway.json")).unwrap())
                .unwrap();
        assert!(gateway["platforms"].get("wecom").is_none());
        assert!(gateway["platforms"].get("weixin").is_some());
        let directory: Value = serde_json::from_str(
            &std::fs::read_to_string(home.join("channel_directory.json")).unwrap(),
        )
        .unwrap();
        assert!(directory["platforms"].get("slack").is_none());
        assert!(directory["platforms"].get("telegram").is_some());
        assert!(home.join("cron").join("jobs.json").exists());
        assert!(home.join("sessions").join("sessions.json").exists());
        assert!(home
            .join("profiles")
            .join("discord")
            .join("sessions")
            .join("old.jsonl")
            .exists());
        assert!(!home.join("feishu_seen_message_ids.json").exists());
        let _ = std::fs::remove_dir_all(data_dir);
    }
}
