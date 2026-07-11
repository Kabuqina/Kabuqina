// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Tauri proxy commands for the trusted STUDY desktop API.

use crate::chat::DeskBridgeError;
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

fn validate_structured_id(id: &str) -> Result<(), DeskBridgeError> {
    validate_study_path_id(id)
        .map_err(|detail| DeskBridgeError::invalid("invalid_study_id", detail))
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
pub async fn cmd_study_drafts(
    app: AppHandle,
    kind: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    let path = match kind {
        Some(k) if !k.trim().is_empty() => {
            validate_study_path_id(k.trim())
                .map_err(|detail| DeskBridgeError::invalid("invalid_study_id", detail))?;
            format!(
                "/api/desk/study/drafts?kind={}&limit={}&offset={}",
                k.trim(),
                limit.unwrap_or(50),
                offset.unwrap_or(0)
            )
        }
        _ => format!(
            "/api/desk/study/drafts?limit={}&offset={}",
            limit.unwrap_or(50),
            offset.unwrap_or(0)
        ),
    };
    crate::chat::desk_json_request_structured(&app, reqwest::Method::GET, &path, None).await
}

#[tauri::command]
pub async fn cmd_study_artifact_summaries(
    app: AppHandle,
    space_id: Option<String>,
    kind: Option<String>,
    status: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    let mut query = vec![
        format!("limit={}", limit.unwrap_or(50)),
        format!("offset={}", offset.unwrap_or(0)),
    ];
    for (name, value) in [("space_id", space_id), ("kind", kind), ("status", status)] {
        if let Some(value) = value.filter(|v| !v.trim().is_empty()) {
            validate_study_path_id(value.trim())
                .map_err(|detail| DeskBridgeError::invalid("invalid_study_id", detail))?;
            query.push(format!("{name}={}", value.trim()));
        }
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/artifacts?{}", query.join("&")),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_artifact_detail(
    app: AppHandle,
    artifact_id: String,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/artifacts/{artifact_id}?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_artifact_status(
    app: AppHandle,
    artifact_id: String,
    space_id: String,
    status: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/artifacts/{artifact_id}/status"),
        Some(json!({"status": status, "space_id": space_id})),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_wrongbook(
    app: AppHandle,
    space_id: String,
    limit: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!(
            "/api/desk/study/wrongbook?space_id={space_id}&limit={}",
            limit.unwrap_or(50)
        ),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_activities(
    app: AppHandle,
    space_id: String,
    limit: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!(
            "/api/desk/study/activities?space_id={space_id}&limit={}",
            limit.unwrap_or(50)
        ),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_data_export(app: AppHandle) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        "/api/desk/study/data/export",
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_data_import(
    app: AppHandle,
    bundle: Value,
) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/data/import",
        Some(json!({"bundle": bundle})),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_data_delete(
    app: AppHandle,
    confirm: String,
) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::DELETE,
        "/api/desk/study/data",
        Some(json!({"confirm": confirm})),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migration_status(app: AppHandle) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        "/api/desk/study/migrations/status",
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migration_failures_export(app: AppHandle) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        "/api/desk/study/migrations/failures/export",
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_student_state_get(
    app: AppHandle,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/student-state?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_student_state_put(
    app: AppHandle,
    space_id: String,
    state: Value,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::PUT,
        "/api/desk/study/student-state",
        Some(json!({ "space_id": space_id, "state": state })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_migrate_context(
    app: AppHandle,
    space_id: String,
    context: Value,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/migrations/context",
        Some(json!({ "space_id": space_id, "context": context })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_evaluations(
    app: AppHandle,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/evaluations?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_evaluation_detail(
    app: AppHandle,
    artifact_id: String,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/evaluations/{artifact_id}?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_learning_plans(
    app: AppHandle,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/learning-plans?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_plan_items(
    app: AppHandle,
    artifact_id: String,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/learning-plans/{artifact_id}/items?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_plan_item_complete(
    app: AppHandle,
    item_id: String,
    space_id: String,
    note: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&item_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/learning-plans/items/{item_id}/complete"),
        Some(json!({ "space_id": space_id, "note": note })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_plan_item_skip(
    app: AppHandle,
    item_id: String,
    space_id: String,
    note: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&item_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/learning-plans/items/{item_id}/skip"),
        Some(json!({ "space_id": space_id, "note": note })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_review_reminder_get(app: AppHandle) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::GET,
        "/api/desk/study/review-reminder",
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_review_reminder_put(
    app: AppHandle,
    enabled: bool,
    time_of_day: String,
) -> Result<Value, String> {
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::PUT,
        "/api/desk/study/review-reminder",
        Some(json!({ "enabled": enabled, "time_of_day": time_of_day })),
    )
    .await
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
pub async fn cmd_study_quiz_generate_practice(
    app: AppHandle,
    artifact_id: String,
    item_id: String,
    practice_kind: String,
) -> Result<Value, String> {
    validate_study_path_id(&artifact_id)?;
    validate_study_path_id(&item_id)?;
    if !matches!(practice_kind.as_str(), "transcribe" | "variant") {
        return Err("invalid practice kind".to_string());
    }
    crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/quizzes/{artifact_id}/practice"),
        Some(json!({ "item_id": item_id, "practice_kind": practice_kind })),
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
        assert!(validate_study_path_id("plan_01:phase-00:task-01").is_ok());
        assert!(validate_study_path_id("").is_err());
        assert!(validate_study_path_id("../etc/passwd").is_err());
        assert!(validate_study_path_id("abc/def").is_err());
        assert!(validate_study_path_id("abc?kind=x").is_err());
        assert!(validate_study_path_id("abc def").is_err());
    }

    #[test]
    fn structured_id_validation_preserves_the_bridge_error_contract() {
        let error = validate_structured_id("../space").unwrap_err();
        assert_eq!(error.status, Some(400));
        assert_eq!(error.code, "invalid_study_id");
        assert_eq!(error.detail, "invalid study id");
    }
}
