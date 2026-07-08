// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Tauri proxy commands for the trusted STUDY desktop API.

use serde_json::{json, Value};
use tauri::AppHandle;

fn validate_study_path_id(id: &str) -> Result<(), String> {
    let ok = !id.is_empty()
        && id.len() <= 200
        && id
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b':'));
    if ok {
        Ok(())
    } else {
        Err("invalid study id".to_string())
    }
}

#[tauri::command]
pub async fn cmd_study_spaces(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(&app, reqwest::Method::GET, "/api/desk/study/spaces", None).await
}

#[tauri::command]
pub async fn cmd_study_space_create(app: AppHandle, title: String) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/spaces",
        Some(json!({ "title": title })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_space_select(app: AppHandle, space_id: String) -> Result<Value, String> {
    validate_study_path_id(&space_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/spaces/{space_id}/select"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_drafts(app: AppHandle, kind: Option<String>) -> Result<Value, String> {
    let path = match kind {
        Some(k) if !k.trim().is_empty() => {
            validate_study_path_id(k.trim())?;
            format!("/api/desk/study/drafts?kind={}", k.trim())
        }
        _ => "/api/desk/study/drafts".to_string(),
    };
    crate::chat::desk_json_request(&app, reqwest::Method::GET, &path, None).await
}

#[tauri::command]
pub async fn cmd_study_artifact_activate(
    app: AppHandle,
    artifact_id: String,
) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/artifacts/{artifact_id}/activate"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_artifact_reject(
    app: AppHandle,
    artifact_id: String,
) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/artifacts/{artifact_id}/reject"),
        None,
    )
    .await
}

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
pub async fn cmd_study_flashcard_capture(app: AppHandle, body: Value) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/flashcards/capture",
        Some(body),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_flashcard_review(
    app: AppHandle,
    item_id: String,
    grade: String,
) -> Result<Value, String> {
    validate_study_path_id(&item_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/flashcards/review",
        Some(json!({ "item_id": item_id, "grade": grade })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migrate_flashcards(app: AppHandle, deck: Value) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/migrations/flashcards",
        Some(json!({ "deck": deck })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_quizzes(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(&app, reqwest::Method::GET, "/api/desk/study/quizzes", None)
        .await
}

#[tauri::command]
pub async fn cmd_study_quiz_questions(
    app: AppHandle,
    artifact_id: String,
) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/quizzes/{artifact_id}/questions"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_quiz_submit(
    app: AppHandle,
    artifact_id: String,
    responses: Value,
) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/quizzes/{artifact_id}/submit"),
        Some(json!({ "responses": responses })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migrate_quizzes(app: AppHandle, quiz: Value) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/migrations/quizzes",
        Some(json!({ "quiz": quiz })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migrate_builtin_course(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/migrations/builtin-course",
        None,
    )
    .await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn study_path_id_validation_rejects_path_and_query_chars() {
        assert!(validate_study_path_id("abc123DEF-_:").is_ok());
        assert!(validate_study_path_id("deck-0001").is_ok());
        assert!(validate_study_path_id("quiz_01:question-0001").is_ok());
        assert!(validate_study_path_id("").is_err());
        assert!(validate_study_path_id("../etc/passwd").is_err());
        assert!(validate_study_path_id("abc/def").is_err());
        assert!(validate_study_path_id("abc?kind=x").is_err());
        assert!(validate_study_path_id("abc def").is_err());
    }
}
