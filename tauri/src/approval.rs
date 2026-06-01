// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! In-app approval dialogs (shell / messaging / cron) via webview events.

use std::collections::HashMap;
use std::sync::Arc;

use rand::RngCore;
use tauri::{AppHandle, Emitter};
use tokio::sync::{Mutex, oneshot};

pub const EVENT_NAME: &str = "hermes-approval-request";

#[derive(Clone, serde::Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ApprovalRequestEvent {
    pub id: String,
    pub kind: String,
    pub reason: Option<String>,
    pub command: Option<String>,
    pub cwd: Option<String>,
    pub target: Option<String>,
    pub content_preview: Option<String>,
    pub schedule: Option<String>,
    pub description: Option<String>,
    pub delivery_target: Option<String>,
}

pub struct ApprovalStore {
    pending: Mutex<HashMap<String, oneshot::Sender<bool>>>,
}

impl ApprovalStore {
    pub fn new() -> Arc<Self> {
        Arc::new(Self {
            pending: Mutex::new(HashMap::new()),
        })
    }

    async fn request(&self, app: &AppHandle, mut payload: ApprovalRequestEvent) -> bool {
        let id = random_id();
        payload.id = id.clone();
        let (tx, rx) = oneshot::channel();
        self.pending.lock().await.insert(id.clone(), tx);
        crate::companion::focus_main_window(app);
        if let Err(e) = app.emit(EVENT_NAME, &payload) {
            log::warn!("approval emit failed: {e}");
            self.pending.lock().await.remove(&id);
            return false;
        }
        rx.await.unwrap_or(false)
    }

    pub async fn respond(&self, id: &str, allowed: bool) -> Result<(), String> {
        let tx = self.pending.lock().await.remove(id);
        match tx {
            Some(tx) => {
                let _ = tx.send(allowed);
                Ok(())
            }
            None => Err(format!("approval {id} not found or already resolved")),
        }
    }
}

fn random_id() -> String {
    let mut buf = [0u8; 16];
    rand::thread_rng().fill_bytes(&mut buf);
    hex::encode(buf)
}

pub async fn ask_shell(
    app: &AppHandle,
    store: &ApprovalStore,
    cmd: &str,
    cwd: &str,
    reason: &str,
) -> bool {
    store
        .request(
            app,
            ApprovalRequestEvent {
                id: String::new(),
                kind: "shell".into(),
                reason: if reason.is_empty() {
                    None
                } else {
                    Some(reason.to_string())
                },
                command: Some(cmd.to_string()),
                cwd: Some(cwd.to_string()),
                target: None,
                content_preview: None,
                schedule: None,
                description: None,
                delivery_target: None,
            },
        )
        .await
}

pub async fn ask_messaging(
    app: &AppHandle,
    store: &ApprovalStore,
    target: &str,
    content_preview: &str,
) -> bool {
    let preview = if content_preview.len() > 300 {
        format!("{}…", &content_preview[..300])
    } else {
        content_preview.to_string()
    };
    store
        .request(
            app,
            ApprovalRequestEvent {
                id: String::new(),
                kind: "messaging".into(),
                reason: None,
                command: None,
                cwd: None,
                target: Some(target.to_string()),
                content_preview: Some(preview),
                schedule: None,
                description: None,
                delivery_target: None,
            },
        )
        .await
}

pub async fn ask_cron(
    app: &AppHandle,
    store: &ApprovalStore,
    schedule: &str,
    description: &str,
    delivery_target: &str,
) -> bool {
    store
        .request(
            app,
            ApprovalRequestEvent {
                id: String::new(),
                kind: "cron".into(),
                reason: None,
                command: None,
                cwd: None,
                target: None,
                content_preview: None,
                schedule: Some(schedule.to_string()),
                description: if description.is_empty() {
                    None
                } else {
                    Some(description.to_string())
                },
                delivery_target: if delivery_target.is_empty() {
                    None
                } else {
                    Some(delivery_target.to_string())
                },
            },
        )
        .await
}

#[tauri::command]
pub async fn cmd_respond_approval(
    state: tauri::State<'_, crate::AppState>,
    id: String,
    allowed: bool,
) -> Result<(), String> {
    state.approval_store.respond(&id, allowed).await
}
