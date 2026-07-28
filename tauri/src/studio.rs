// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Studio commands proxying the trusted loopback desk API.

use crate::chat::DeskBridgeError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tauri::AppHandle;

fn validate_id(value: &str, label: &str) -> Result<(), DeskBridgeError> {
    if value.is_empty()
        || value.len() > 200
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b'.' | b':'))
    {
        return Err(DeskBridgeError::invalid(
            "invalid_studio_id",
            format!("invalid {label}"),
        ));
    }
    Ok(())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StudioSourceRef {
    kind: String,
    space_id: String,
    artifact_id: String,
}

#[tauri::command]
pub async fn cmd_studio_projects(app: AppHandle) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        "/api/desk/studio/projects",
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_studio_create_project(
    app: AppHandle,
    title: String,
) -> Result<Value, DeskBridgeError> {
    let title = title.trim();
    if title.is_empty() || title.chars().count() > 200 {
        return Err(DeskBridgeError::invalid(
            "studio_invalid_request",
            "title must contain 1-200 characters",
        ));
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/studio/projects",
        Some(json!({"title": title})),
    )
    .await
}

#[tauri::command]
pub async fn cmd_studio_save_brief(
    app: AppHandle,
    project_id: String,
    brief: String,
) -> Result<Value, DeskBridgeError> {
    validate_id(&project_id, "project id")?;
    if brief.chars().count() > 20_000 {
        return Err(DeskBridgeError::invalid(
            "studio_invalid_request",
            "brief is too long",
        ));
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/studio/projects/{project_id}/brief"),
        Some(json!({"brief": brief})),
    )
    .await
}

#[tauri::command]
pub async fn cmd_studio_gather_sources(
    app: AppHandle,
    project_id: String,
    refs: Vec<StudioSourceRef>,
) -> Result<Value, DeskBridgeError> {
    validate_id(&project_id, "project id")?;
    if refs.is_empty() || refs.len() > 100 {
        return Err(DeskBridgeError::invalid(
            "studio_invalid_request",
            "refs must contain 1-100 sources",
        ));
    }
    for source in &refs {
        if source.kind != "study_artifact" {
            return Err(DeskBridgeError::invalid(
                "studio_invalid_request",
                "only study_artifact sources are supported",
            ));
        }
        validate_id(&source.space_id, "space id")?;
        validate_id(&source.artifact_id, "artifact id")?;
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/studio/projects/{project_id}/sources"),
        Some(json!({"refs": refs})),
    )
    .await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn studio_ids_reject_path_injection() {
        assert!(validate_id("project-1", "project id").is_ok());
        assert!(validate_id("../project", "project id").is_err());
        assert!(validate_id("project/brief", "project id").is_err());
    }
}
