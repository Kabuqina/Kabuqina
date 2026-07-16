// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Read-only view of QQ Bot credentials in ``kabuqina-home/.env`` (no secrets in IPC payloads).

use std::path::PathBuf;
use tauri::AppHandle;

/// Whether ``QQ_APP_ID`` + ``QQ_CLIENT_SECRET`` are set (secret value is never returned).
#[tauri::command]
pub fn cmd_qq_env_status(
    app: AppHandle,
) -> Result<crate::gateway_supervisor::QqEnvSnapshot, String> {
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;
    let hh = crate::gateway_supervisor::kabuqina_home_path(&data_dir);
    Ok(crate::gateway_supervisor::read_qq_env_snapshot(&hh))
}

/// Remove QQ Bot env vars from ``kabuqina-home/.env``.
#[tauri::command]
pub fn cmd_qq_env_remove(app: AppHandle) -> Result<(), String> {
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;
    let hh = crate::gateway_supervisor::kabuqina_home_path(&data_dir);
    let env_path: PathBuf = hh.join(".env");
    let content = std::fs::read_to_string(&env_path).unwrap_or_default();
    let lines: Vec<String> = content
        .lines()
        .map(|l| l.to_string())
        .filter(|line| {
            let trimmed = line.trim();
            !trimmed.starts_with("QQ_")
        })
        .collect();
    std::fs::write(&env_path, lines.join("\n") + "\n").map_err(|e| e.to_string())
}
