// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Tauri proxy commands for the trusted STUDY desktop API.

use crate::chat::DeskBridgeError;
use serde_json::{json, Value};
use std::path::Path;
use tauri::AppHandle;

const STUDY_IMPORT_FILE_MAX_BYTES: u64 = 10 * 1024 * 1024;

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
    space_id: String,
    kind: Option<String>,
    status: Option<String>,
    limit: Option<u32>,
    offset: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    let mut query = vec![
        format!("space_id={space_id}"),
        format!("limit={}", limit.unwrap_or(50)),
        format!("offset={}", offset.unwrap_or(0)),
    ];
    for (name, value) in [("kind", kind), ("status", status)] {
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
pub async fn cmd_study_artifact_source_audit(
    app: AppHandle,
    artifact_id: String,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/artifacts/{artifact_id}/source-audit?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_artifact_semantic_review(
    app: AppHandle,
    artifact_id: String,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/artifacts/{artifact_id}/semantic-review"),
        Some(json!({ "space_id": space_id })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_knowledge_points(
    app: AppHandle,
    space_id: String,
    limit: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    let limit = limit.unwrap_or(50).clamp(1, 100);
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/knowledge-points?space_id={space_id}&limit={limit}"),
        None,
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

fn read_study_import_file(path_str: &str) -> Result<Value, DeskBridgeError> {
    let path = Path::new(path_str);
    if !path.is_absolute()
        || !path
            .extension()
            .and_then(|extension| extension.to_str())
            .is_some_and(|extension| extension.eq_ignore_ascii_case("json"))
    {
        return Err(DeskBridgeError::invalid(
            "study_invalid_import_file",
            "choose an absolute .json backup file",
        ));
    }
    let metadata = std::fs::metadata(path).map_err(|_| {
        DeskBridgeError::invalid("study_invalid_import_file", "backup file cannot be read")
    })?;
    if !metadata.is_file() || metadata.len() > STUDY_IMPORT_FILE_MAX_BYTES {
        return Err(DeskBridgeError::invalid(
            "study_invalid_import_file",
            "backup file is not a supported size",
        ));
    }
    let text = std::fs::read_to_string(path).map_err(|_| {
        DeskBridgeError::invalid("study_invalid_import_file", "backup file must be UTF-8")
    })?;
    let bundle: Value = serde_json::from_str(&text).map_err(|_| {
        DeskBridgeError::invalid("study_invalid_import_file", "backup file is not valid JSON")
    })?;
    if !bundle.is_object() || bundle.get("version").and_then(Value::as_u64) != Some(1) {
        return Err(DeskBridgeError::invalid(
            "study_invalid_import_file",
            "backup file must be a version 1 study bundle",
        ));
    }
    Ok(bundle)
}

/// Read a backup chosen through the native dialog. This command intentionally
/// returns only a validated v1 JSON object; it never writes or imports data.
#[tauri::command]
pub fn cmd_study_data_import_file(path_str: String) -> Result<Value, DeskBridgeError> {
    read_study_import_file(&path_str)
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
pub async fn cmd_study_flashcards(
    app: AppHandle,
    space_id: String,
    due_only: Option<bool>,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    let path = if due_only.unwrap_or(false) {
        format!("/api/desk/study/flashcards?space_id={space_id}&due_only=true")
    } else {
        format!("/api/desk/study/flashcards?space_id={space_id}")
    };
    crate::chat::desk_json_request_structured(&app, reqwest::Method::GET, &path, None).await
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
    space_id: String,
    item_id: String,
    grade: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    validate_structured_id(&item_id)?;
    if !matches!(grade.as_str(), "again" | "hard" | "good" | "easy") {
        return Err(DeskBridgeError::invalid("study_invalid_request", "invalid review grade"));
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/flashcards/review",
        Some(json!({ "space_id": space_id, "item_id": item_id, "grade": grade })),
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
pub async fn cmd_study_quizzes(
    app: AppHandle,
    space_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/quizzes?space_id={space_id}"),
        None,
    ).await
}

#[tauri::command]
pub async fn cmd_study_quiz_questions(
    app: AppHandle,
    space_id: String,
    artifact_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    validate_structured_id(&artifact_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/quizzes/{artifact_id}/questions?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_quiz_submit(
    app: AppHandle,
    space_id: String,
    artifact_id: String,
    responses: Value,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    validate_structured_id(&artifact_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/quizzes/{artifact_id}/submit"),
        Some(json!({ "space_id": space_id, "responses": responses })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_quiz_generate_practice(
    app: AppHandle,
    space_id: String,
    artifact_id: String,
    item_id: String,
    practice_kind: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    validate_structured_id(&artifact_id)?;
    validate_structured_id(&item_id)?;
    if !matches!(practice_kind.as_str(), "transcribe" | "variant") {
        return Err(DeskBridgeError::invalid("study_invalid_request", "invalid practice kind"));
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/quizzes/{artifact_id}/practice"),
        Some(json!({ "space_id": space_id, "item_id": item_id, "practice_kind": practice_kind })),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_practice_source(
    app: AppHandle,
    space_id: String,
    activity_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    validate_structured_id(&activity_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/practice-source?space_id={space_id}&activity_id={activity_id}"),
        None,
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

    fn assert_invalid_import_file(result: Result<Value, DeskBridgeError>) {
        let error = result.unwrap_err();
        assert_eq!(error.status, Some(400));
        assert_eq!(error.code, "study_invalid_import_file");
    }

    fn import_test_root(case: &str) -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!(
            "kabuqina-study-import-{}-{case}",
            std::process::id()
        ));
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();
        root
    }

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

    #[test]
    fn study_import_file_requires_a_small_v1_json_object() {
        let root = import_test_root("valid-version");
        let valid = root.join("backup.json");
        std::fs::write(&valid, r#"{"version":1,"spaces":[]}"#).unwrap();
        assert!(read_study_import_file(&valid.display().to_string()).is_ok());

        let invalid_version = root.join("invalid.json");
        std::fs::write(&invalid_version, r#"{"version":2}"#).unwrap();
        assert_invalid_import_file(read_study_import_file(
            &invalid_version.display().to_string(),
        ));

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn study_import_file_rejects_relative_paths_and_non_json_extensions() {
        assert_invalid_import_file(read_study_import_file("backup.json"));

        let root = import_test_root("path-extension");
        let wrong_extension = root.join("backup.txt");
        std::fs::write(&wrong_extension, r#"{"version":1}"#).unwrap();
        assert_invalid_import_file(read_study_import_file(
            &wrong_extension.display().to_string(),
        ));
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn study_import_file_rejects_oversized_non_utf8_and_invalid_json_files() {
        let root = import_test_root("content-validation");

        let oversized = root.join("oversized.json");
        std::fs::File::create(&oversized)
            .unwrap()
            .set_len(STUDY_IMPORT_FILE_MAX_BYTES + 1)
            .unwrap();
        assert_invalid_import_file(read_study_import_file(&oversized.display().to_string()));

        let non_utf8 = root.join("non-utf8.json");
        std::fs::write(&non_utf8, [0xff, 0xfe, 0xfd]).unwrap();
        assert_invalid_import_file(read_study_import_file(&non_utf8.display().to_string()));

        let invalid_json = root.join("invalid-json.json");
        std::fs::write(&invalid_json, "not json").unwrap();
        assert_invalid_import_file(read_study_import_file(&invalid_json.display().to_string()));

        let _ = std::fs::remove_dir_all(&root);
    }
}
