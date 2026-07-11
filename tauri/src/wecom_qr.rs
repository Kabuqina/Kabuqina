// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Route C: short-lived bundled Python process for WeCom scan-to-create QR flow (`wecom_qr_worker.py`).

use serde_json::{json, Value};
use std::path::PathBuf;
use tauri::AppHandle;
use tokio::io::{AsyncBufReadExt, BufReader};

const PROGRESS_FILE: &str = "wecom_qr_progress.json";
const RESULT_FILE: &str = "wecom_qr_result.json";

fn progress_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(crate::paths::ensure_data_dir(app)
        .map_err(|e| e.to_string())?
        .join(PROGRESS_FILE))
}

fn result_path(app: &AppHandle) -> Result<PathBuf, String> {
    Ok(crate::paths::ensure_data_dir(app)
        .map_err(|e| e.to_string())?
        .join(RESULT_FILE))
}

async fn read_json_file(path: &PathBuf) -> Option<Value> {
    let s = tokio::fs::read_to_string(path).await.ok()?;
    serde_json::from_str(&s).ok()
}

/// Start `python.exe wecom_qr_worker.py` (CREATE_NO_WINDOW on Windows). Clears prior progress/result.
#[tauri::command]
pub async fn cmd_wecom_qr_start(
    app: AppHandle,
    state: tauri::State<'_, crate::AppState>,
) -> Result<(), String> {
    let _ = tokio::fs::remove_file(progress_path(&app)?).await;
    let _ = tokio::fs::remove_file(result_path(&app)?).await;

    let bundle = crate::paths::resolve_runtime_dir(&app).map_err(|e| e.to_string())?;
    let worker = bundle.join("wecom_qr_worker.py");
    if !worker.exists() {
        return Err(
            "wecom_qr_worker.py is missing from the runtime bundle. Rebuild the Python bundle."
                .into(),
        );
    }
    let py = bundle.join("python").join("python.exe");
    if !py.exists() {
        return Err("bundled python.exe not found".into());
    }

    let mut slot = state.wecom_qr_child.lock().await;
    if let Some(mut c) = slot.take() {
        let _ = c.start_kill();
    }

    let workspace = crate::paths::ensure_workspace(&app).map_err(|e| e.to_string())?;
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;

    let mut cmd = tokio::process::Command::new(&py);
    #[cfg(windows)]
    {
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.arg(&worker)
        .current_dir(&bundle)
        .env("KABUQINA_BUNDLE_DIR", &bundle)
        .env("KABUQINA_DATA_DIR", &data_dir)
        .env("KABUQINA_WORKSPACE", &workspace)
        .env("HERMESDESK_BUNDLE_DIR", &bundle)
        .env("HERMESDESK_DATA_DIR", &data_dir)
        .env("HERMESDESK_WORKSPACE", &workspace)
        .env("PYTHONIOENCODING", "utf-8")
        .env_remove("PYTHONPATH")
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::piped())
        .stderr(std::process::Stdio::piped());

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("spawn wecom QR worker: {e}"))?;

    if let Some(out) = child.stdout.take() {
        let tag = "wecom-qr.out";
        tokio::spawn(async move {
            let mut lines = BufReader::new(out).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                log::info!("{tag}: {line}");
            }
        });
    }
    if let Some(err) = child.stderr.take() {
        let tag = "wecom-qr.err";
        tokio::spawn(async move {
            let mut lines = BufReader::new(err).lines();
            while let Ok(Some(line)) = lines.next_line().await {
                log::info!("{tag}: {line}");
            }
        });
    }

    *slot = Some(child);
    Ok(())
}

/// Poll worker state: `running`, optional `progress` / `result` JSON from the data dir.
#[tauri::command]
pub async fn cmd_wecom_qr_status(
    app: AppHandle,
    state: tauri::State<'_, crate::AppState>,
) -> Result<serde_json::Value, String> {
    let mut running = false;
    {
        let mut slot = state.wecom_qr_child.lock().await;
        if let Some(ref mut child) = *slot {
            match child.try_wait() {
                Ok(None) => running = true,
                Ok(Some(_)) => {
                    let _ = slot.take();
                }
                Err(_) => {
                    let _ = slot.take();
                }
            }
        }
    }
    let progress = read_json_file(&progress_path(&app)?).await;
    let result = read_json_file(&result_path(&app)?).await;
    Ok(json!({
        "running": running,
        "progress": progress,
        "result": result,
    }))
}

/// Cancel a running WeCom QR process (SIGKILL).
#[tauri::command]
pub async fn cmd_wecom_qr_cancel(state: tauri::State<'_, crate::AppState>) -> Result<(), String> {
    let mut slot = state.wecom_qr_child.lock().await;
    if let Some(mut child) = slot.take() {
        let _ = child.start_kill();
    }
    Ok(())
}
