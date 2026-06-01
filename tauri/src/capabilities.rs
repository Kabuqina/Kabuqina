// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Shell → Hermes capability catalog proxy.

use crate::chat;
use serde_json::Value;
use tauri::AppHandle;
use url::form_urlencoded;

async fn authed_get(app: &AppHandle, path: &str) -> Result<Value, String> {
    let base = chat::hermes_base(app).await?;
    let token = chat::desk_auth_header(app).await?;
    let client = chat::http_client();
    let mut req = client
        .get(format!("{base}{path}"))
        .header("X-HermesDesk-Auth", &token);
    if let Some(bearer) = chat::hermes_bearer_resolved(app).await {
        req = req.header("Authorization", format!("Bearer {bearer}"));
    }
    let res = req
        .send()
        .await
        .map_err(|e| format!("Hermes request failed: {e}"))?;
    chat::desk_response_json(res).await
}

#[tauri::command]
pub async fn cmd_capabilities_catalog(app: AppHandle) -> Result<Value, String> {
    authed_get(&app, "/api/hermesdesk/capabilities").await
}

#[tauri::command]
pub async fn cmd_capability_skill_detail(app: AppHandle, name: String) -> Result<Value, String> {
    let encoded: String = form_urlencoded::byte_serialize(name.as_bytes()).collect();
    authed_get(&app, &format!("/api/hermesdesk/skills/{encoded}")).await
}
