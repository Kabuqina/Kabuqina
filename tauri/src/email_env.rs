// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Read / write EMAIL_* env vars in ``hermes-home/.env``.

use std::collections::HashSet;
use std::path::PathBuf;
use tauri::AppHandle;

const EMAIL_ENV_PREFIXES: &[&str] = &[
    "EMAIL_ADDRESS=",
    "EMAIL_ADDRESS ",
    "EMAIL_PASSWORD=",
    "EMAIL_PASSWORD ",
    "EMAIL_AUTH_MODE=",
    "EMAIL_AUTH_MODE ",
    "EMAIL_OAUTH2_ACCESS_TOKEN=",
    "EMAIL_OAUTH2_ACCESS_TOKEN ",
    "EMAIL_OAUTH2_REFRESH_TOKEN=",
    "EMAIL_OAUTH2_REFRESH_TOKEN ",
    "EMAIL_OAUTH2_CLIENT_ID=",
    "EMAIL_OAUTH2_CLIENT_ID ",
    "EMAIL_OAUTH2_CLIENT_SECRET=",
    "EMAIL_OAUTH2_CLIENT_SECRET ",
    "EMAIL_OAUTH2_TENANT=",
    "EMAIL_OAUTH2_TENANT ",
    "EMAIL_OAUTH2_TOKEN_URL=",
    "EMAIL_OAUTH2_TOKEN_URL ",
    "EMAIL_OAUTH2_SCOPE=",
    "EMAIL_OAUTH2_SCOPE ",
    "EMAIL_IMAP_HOST=",
    "EMAIL_IMAP_HOST ",
    "EMAIL_SMTP_HOST=",
    "EMAIL_SMTP_HOST ",
    "EMAIL_IMAP_PORT=",
    "EMAIL_IMAP_PORT ",
    "EMAIL_SMTP_PORT=",
    "EMAIL_SMTP_PORT ",
    "EMAIL_POLL_INTERVAL=",
    "EMAIL_ALLOWED_USERS=",
    "EMAIL_ALLOWED_USERS ",
    "EMAIL_ALLOW_ALL_USERS=",
    "EMAIL_ALLOW_ALL_USERS ",
    "EMAIL_HOME_ADDRESS=",
    "EMAIL_HOME_ADDRESS ",
    "EMAIL_HOME_ADDRESS_NAME=",
];

fn hh(app: &AppHandle) -> Result<PathBuf, String> {
    let data_dir = crate::paths::ensure_data_dir(app).map_err(|e| e.to_string())?;
    Ok(crate::gateway_supervisor::hermes_home_path(&data_dir))
}

#[derive(serde::Serialize)]
pub struct EmailEnvSnapshot {
    pub configured: bool,
    pub auth_mode: String,
    pub has_address: bool,
    pub has_password: bool,
    pub has_oauth2_access_token: bool,
    pub has_oauth2_refresh_token: bool,
    pub has_oauth2_client_id: bool,
    pub has_imap_host: bool,
    pub has_smtp_host: bool,
    pub address_hint: Option<String>,
}

#[tauri::command]
pub fn cmd_email_env_status(app: AppHandle) -> Result<EmailEnvSnapshot, String> {
    let hh = hh(&app)?;
    let keys = crate::gateway_supervisor::parse_dotenv_upper(&hh);
    let nonempty = |k: &str| keys.get(k).map(|s| !s.is_empty()).unwrap_or(false);
    let address = keys.get("EMAIL_ADDRESS").cloned();
    let has_address = nonempty("EMAIL_ADDRESS");
    let has_password = nonempty("EMAIL_PASSWORD");
    let has_oauth2_access_token = nonempty("EMAIL_OAUTH2_ACCESS_TOKEN");
    let has_oauth2_refresh_token = nonempty("EMAIL_OAUTH2_REFRESH_TOKEN");
    let has_oauth2_client_id = nonempty("EMAIL_OAUTH2_CLIENT_ID");
    let has_imap_host = nonempty("EMAIL_IMAP_HOST");
    let has_smtp_host = nonempty("EMAIL_SMTP_HOST");
    let auth_mode = keys
        .get("EMAIL_AUTH_MODE")
        .map(|s| s.trim().to_ascii_lowercase())
        .unwrap_or_else(|| "password".to_string());
    let auth_ready = if auth_mode == "oauth2" || auth_mode == "xoauth2" {
        has_oauth2_access_token || (has_oauth2_refresh_token && has_oauth2_client_id)
    } else {
        has_password
    };
    let configured = has_address && auth_ready && has_imap_host && has_smtp_host;
    let address_hint = address.map(|a| {
        let ch: Vec<char> = a.trim().chars().collect();
        if ch.len() <= 6 {
            return a;
        }
        format!(
            "{}…{}",
            ch[..3].iter().collect::<String>(),
            ch[ch.len() - 4..].iter().collect::<String>()
        )
    });
    Ok(EmailEnvSnapshot {
        configured,
        auth_mode,
        has_address,
        has_password,
        has_oauth2_access_token,
        has_oauth2_refresh_token,
        has_oauth2_client_id,
        has_imap_host,
        has_smtp_host,
        address_hint,
    })
}

#[tauri::command]
pub fn cmd_email_save_config(
    app: AppHandle,
    address: String,
    password: String,
    imap_host: String,
    smtp_host: String,
    auth_mode: Option<String>,
    oauth2_access_token: Option<String>,
    oauth2_refresh_token: Option<String>,
    oauth2_client_id: Option<String>,
    oauth2_client_secret: Option<String>,
    oauth2_tenant: Option<String>,
    oauth2_token_url: Option<String>,
    oauth2_scope: Option<String>,
) -> Result<(), String> {
    let address = address.trim().to_string();
    let password = password.trim().to_string();
    let imap_host = imap_host.trim().to_string();
    let smtp_host = smtp_host.trim().to_string();
    let auth_mode = auth_mode
        .unwrap_or_else(|| "password".to_string())
        .trim()
        .to_ascii_lowercase();
    let oauth2_access_token = oauth2_access_token.unwrap_or_default().trim().to_string();
    let oauth2_refresh_token = oauth2_refresh_token.unwrap_or_default().trim().to_string();
    let oauth2_client_id = oauth2_client_id.unwrap_or_default().trim().to_string();
    let oauth2_client_secret = oauth2_client_secret.unwrap_or_default().trim().to_string();
    let oauth2_tenant = oauth2_tenant.unwrap_or_default().trim().to_string();
    let oauth2_token_url = oauth2_token_url.unwrap_or_default().trim().to_string();
    let oauth2_scope = oauth2_scope.unwrap_or_default().trim().to_string();
    if address.is_empty() {
        return Err("EMAIL_ADDRESS must not be empty".into());
    }
    if auth_mode != "password" && auth_mode != "oauth2" && auth_mode != "xoauth2" {
        return Err("EMAIL_AUTH_MODE must be password or oauth2".into());
    }
    if auth_mode == "password" && password.is_empty() {
        return Err("EMAIL_PASSWORD must not be empty".into());
    }
    if (auth_mode == "oauth2" || auth_mode == "xoauth2")
        && oauth2_access_token.is_empty()
        && (oauth2_client_id.is_empty() || oauth2_refresh_token.is_empty())
    {
        return Err("OAuth2 requires an access token or both client id and refresh token".into());
    }
    if imap_host.is_empty() {
        return Err("EMAIL_IMAP_HOST must not be empty".into());
    }
    if smtp_host.is_empty() {
        return Err("EMAIL_SMTP_HOST must not be empty".into());
    }
    crate::validation::validate_env_value(&address)?;
    crate::validation::validate_env_value(&password)?;
    crate::validation::validate_env_value(&imap_host)?;
    crate::validation::validate_env_value(&smtp_host)?;
    crate::validation::validate_env_value(&auth_mode)?;
    crate::validation::validate_env_value(&oauth2_access_token)?;
    crate::validation::validate_env_value(&oauth2_refresh_token)?;
    crate::validation::validate_env_value(&oauth2_client_id)?;
    crate::validation::validate_env_value(&oauth2_client_secret)?;
    crate::validation::validate_env_value(&oauth2_tenant)?;
    crate::validation::validate_env_value(&oauth2_token_url)?;
    crate::validation::validate_env_value(&oauth2_scope)?;

    let hh = hh(&app)?;
    std::fs::create_dir_all(&hh).map_err(|e| e.to_string())?;
    let env_path: PathBuf = hh.join(".env");
    let content = std::fs::read_to_string(&env_path).unwrap_or_default();
    let mut lines: Vec<String> = content.lines().map(|l| l.to_string()).collect();

    let stale_keys: HashSet<&str> = if auth_mode == "password" {
        [
            "EMAIL_OAUTH2_ACCESS_TOKEN",
            "EMAIL_OAUTH2_REFRESH_TOKEN",
            "EMAIL_OAUTH2_CLIENT_ID",
            "EMAIL_OAUTH2_CLIENT_SECRET",
            "EMAIL_OAUTH2_TENANT",
            "EMAIL_OAUTH2_TOKEN_URL",
            "EMAIL_OAUTH2_SCOPE",
        ]
        .into_iter()
        .collect()
    } else {
        ["EMAIL_PASSWORD"].into_iter().collect()
    };

    for line in &mut lines {
        let trimmed = line.trim();
        let Some((raw_key, _)) = trimmed.split_once('=') else {
            continue;
        };
        if stale_keys.contains(raw_key.trim().to_ascii_uppercase().as_str()) {
            *line = String::new();
        }
    }
    lines.retain(|line| !line.is_empty());

    let mut pairs: Vec<(&str, &String)> = vec![
        ("EMAIL_ADDRESS", &address),
        ("EMAIL_AUTH_MODE", &auth_mode),
        ("EMAIL_IMAP_HOST", &imap_host),
        ("EMAIL_SMTP_HOST", &smtp_host),
    ];
    if auth_mode == "password" {
        pairs.push(("EMAIL_PASSWORD", &password));
    } else {
        pairs.push(("EMAIL_OAUTH2_ACCESS_TOKEN", &oauth2_access_token));
        pairs.push(("EMAIL_OAUTH2_REFRESH_TOKEN", &oauth2_refresh_token));
        pairs.push(("EMAIL_OAUTH2_CLIENT_ID", &oauth2_client_id));
        pairs.push(("EMAIL_OAUTH2_CLIENT_SECRET", &oauth2_client_secret));
        pairs.push(("EMAIL_OAUTH2_TENANT", &oauth2_tenant));
        pairs.push(("EMAIL_OAUTH2_TOKEN_URL", &oauth2_token_url));
        pairs.push(("EMAIL_OAUTH2_SCOPE", &oauth2_scope));
    }
    for (key, val) in &pairs {
        let mut found = false;
        for line in &mut lines {
            let trimmed = line.trim();
            if trimmed.starts_with(&format!("{}=", key))
                || trimmed.starts_with(&format!("{} ", key))
            {
                *line = format!("{}={}", key, val);
                found = true;
                break;
            }
        }
        if !found {
            lines.push(format!("{}={}", key, val));
        }
    }
    std::fs::write(&env_path, lines.join("\n") + "\n").map_err(|e| e.to_string())
}

#[tauri::command]
pub fn cmd_email_env_remove(app: AppHandle) -> Result<(), String> {
    let hh = hh(&app)?;
    let env_path: PathBuf = hh.join(".env");
    let content = std::fs::read_to_string(&env_path).unwrap_or_default();
    let lines: Vec<String> = content
        .lines()
        .map(|l| l.to_string())
        .filter(|line| {
            let trimmed = line.trim();
            !EMAIL_ENV_PREFIXES
                .iter()
                .any(|prefix| trimmed.starts_with(prefix))
        })
        .collect();
    std::fs::write(&env_path, lines.join("\n") + "\n").map_err(|e| e.to_string())
}
