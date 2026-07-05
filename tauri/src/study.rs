// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Tauri proxy commands for the trusted STUDY desktop API.

use serde_json::Value;
use tauri::AppHandle;

#[tauri::command]
pub async fn cmd_study_flashcards(app: AppHandle, due_only: Option<bool>) -> Result<Value, String> {
    let path = if due_only.unwrap_or(false) {
        "/api/desk/study/flashcards?due_only=true"
    } else {
        "/api/desk/study/flashcards"
    };
    crate::chat::desk_json_request(&app, reqwest::Method::GET, path, None).await
}

#[tauri::command]
pub async fn cmd_study_flashcard_capture(
    app: AppHandle,
    body: Value,
) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/flashcards/capture",
        Some(body),
    )
    .await
}
