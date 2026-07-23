// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Tauri proxy commands for the trusted STUDY desktop API.

use crate::chat::DeskBridgeError;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use tauri::AppHandle;
use uuid::Uuid;

const STUDY_BUNDLE_FILE_MAX_BYTES: u64 = 24 * 1024 * 1024;

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

fn validate_activity_kind(kind: &str) -> Result<(), DeskBridgeError> {
    if matches!(kind, "tutor" | "review" | "practice") {
        Ok(())
    } else {
        Err(DeskBridgeError::invalid(
            "study_activity_invalid_request",
            "invalid activity kind",
        ))
    }
}

fn validate_activity_wire_id(id: &str) -> Result<(), DeskBridgeError> {
    let valid = !id.is_empty()
        && id.len() <= 128
        && id
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b':' | b'-'));
    if valid {
        Ok(())
    } else {
        Err(DeskBridgeError::invalid(
            "study_activity_invalid_request",
            "invalid Tutor activity id",
        ))
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
pub async fn cmd_study_activity_start(
    app: AppHandle,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/activity-runs",
        Some(body),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_activity_get(
    app: AppHandle,
    space_id: String,
    activity_kind: String,
    activity_id: String,
) -> Result<Value, DeskBridgeError> {
    validate_activity_wire_id(&space_id)?;
    validate_activity_kind(&activity_kind)?;
    validate_activity_wire_id(&activity_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/activity-runs/{activity_kind}/{activity_id}?space_id={space_id}"),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_activity_list(
    app: AppHandle,
    space_id: String,
    activity_kind: String,
    status: Option<String>,
    limit: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    validate_activity_wire_id(&space_id)?;
    validate_activity_kind(&activity_kind)?;
    let limit = limit.unwrap_or(100);
    if !(1..=100).contains(&limit) {
        return Err(DeskBridgeError::invalid(
            "study_activity_invalid_request",
            "limit must be within 1..100",
        ));
    }
    let mut query = vec![
        format!("space_id={space_id}"),
        format!("activity_kind={activity_kind}"),
        format!("limit={limit}"),
    ];
    if let Some(status) = status.filter(|value| !value.trim().is_empty()) {
        validate_activity_wire_id(status.trim())?;
        query.push(format!("status={}", status.trim()));
    }
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::GET,
        &format!("/api/desk/study/activity-runs?{}", query.join("&")),
        None,
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_activity_resume(
    app: AppHandle,
    activity_kind: String,
    activity_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    validate_activity_kind(&activity_kind)?;
    validate_activity_wire_id(&activity_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/activity-runs/{activity_kind}/{activity_id}/resume"),
        Some(body),
    )
    .await
}

#[tauri::command]
pub async fn cmd_study_activity_cancel(
    app: AppHandle,
    activity_kind: String,
    activity_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    validate_activity_kind(&activity_kind)?;
    validate_activity_wire_id(&activity_id)?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/activity-runs/{activity_kind}/{activity_id}/cancel"),
        Some(body),
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
    mode: Option<String>,
) -> Result<Value, DeskBridgeError> {
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/data/import",
        Some(json!({
            "bundle": bundle,
            "mode": mode.unwrap_or_else(|| "replace_empty_owner".to_string())
        })),
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
    let link_metadata = std::fs::symlink_metadata(path).map_err(|_| {
        DeskBridgeError::invalid("study_invalid_import_file", "backup file cannot be read")
    })?;
    if link_metadata.file_type().is_symlink()
        || !link_metadata.is_file()
        || link_metadata.len() > STUDY_BUNDLE_FILE_MAX_BYTES
    {
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
    if !bundle.is_object() || !matches!(bundle.get("version").and_then(Value::as_u64), Some(1 | 2))
    {
        return Err(DeskBridgeError::invalid(
            "study_invalid_import_file",
            "backup file must be a version 1 or 2 study bundle",
        ));
    }
    Ok(bundle)
}

/// Read a backup chosen through the native dialog. This command intentionally
/// returns only a validated v1/v2 JSON object; it never writes or imports data.
#[tauri::command]
pub fn cmd_study_data_import_file(path_str: String) -> Result<Value, DeskBridgeError> {
    read_study_import_file(&path_str)
}

fn canonical_bundle_value(value: &Value) -> Result<Value, DeskBridgeError> {
    use unicode_normalization::UnicodeNormalization;

    match value {
        Value::Null | Value::Bool(_) => Ok(value.clone()),
        Value::String(text) => Ok(Value::String(text.nfc().collect())),
        Value::Number(number) if number.is_i64() || number.is_u64() => {
            Ok(Value::Number(number.clone()))
        }
        Value::Number(_) => Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup bundle contains an unsupported JSON number",
        )),
        Value::Array(items) => Ok(Value::Array(
            items
                .iter()
                .map(canonical_bundle_value)
                .collect::<Result<Vec<_>, _>>()?,
        )),
        Value::Object(object) => {
            let mut normalized = serde_json::Map::new();
            for (key, item) in object {
                let normalized_key: String = key.nfc().collect();
                if normalized.contains_key(&normalized_key) {
                    return Err(DeskBridgeError::invalid(
                        "study_downgrade_backup_failed",
                        "backup bundle contains duplicate normalized keys",
                    ));
                }
                normalized.insert(normalized_key, canonical_bundle_value(item)?);
            }
            Ok(Value::Object(normalized))
        }
    }
}

fn validate_quiz_item_ids(item_ids: Option<&[String]>) -> Result<(), DeskBridgeError> {
    let Some(ids) = item_ids else {
        return Ok(());
    };
    if ids.is_empty() {
        return Err(DeskBridgeError::invalid(
            "study_invalid_request",
            "itemIds must not be empty",
        ));
    }
    let mut seen = HashSet::with_capacity(ids.len());
    for item_id in ids {
        validate_structured_id(item_id)?;
        if !seen.insert(item_id.as_str()) {
            return Err(DeskBridgeError::invalid(
                "study_invalid_request",
                "itemIds must not contain duplicates",
            ));
        }
    }
    Ok(())
}

fn quiz_submit_body(space_id: String, responses: Value, item_ids: Option<Vec<String>>) -> Value {
    let mut body = json!({
        "space_id": space_id,
        "responses": responses,
    });
    if let Some(ids) = item_ids {
        body["item_ids"] = json!(ids);
    }
    body
}

fn canonical_bundle_bytes(bundle: &Value) -> Result<Vec<u8>, DeskBridgeError> {
    let normalized = canonical_bundle_value(bundle)?;
    serde_json::to_vec(&normalized).map_err(|_| {
        DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup bundle cannot be serialized",
        )
    })
}

fn bundle_sha256(bundle: &Value) -> Result<String, DeskBridgeError> {
    Ok(hex::encode(Sha256::digest(canonical_bundle_bytes(bundle)?)))
}

fn validate_backup_destination(path_str: &str) -> Result<PathBuf, DeskBridgeError> {
    let path = PathBuf::from(path_str);
    if !path.is_absolute()
        || !path
            .extension()
            .and_then(|extension| extension.to_str())
            .is_some_and(|extension| extension.eq_ignore_ascii_case("json"))
    {
        return Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "choose an absolute .json backup path",
        ));
    }
    let parent = path.parent().ok_or_else(|| {
        DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup path has no parent directory",
        )
    })?;
    if !parent.is_dir() {
        return Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup parent directory is unavailable",
        ));
    }
    if let Ok(metadata) = std::fs::symlink_metadata(&path) {
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(DeskBridgeError::invalid(
                "study_downgrade_backup_failed",
                "backup destination must be a regular file",
            ));
        }
    }
    Ok(path)
}

fn write_verified_backup_with_hooks<W, H>(
    path_str: &str,
    bundle: &Value,
    expected_sha256: &str,
    mut write_bytes: W,
    after_replace: H,
) -> Result<(), DeskBridgeError>
where
    W: FnMut(&mut File, &[u8]) -> std::io::Result<()>,
    H: FnOnce(&Path) -> std::io::Result<()>,
{
    if expected_sha256.len() != 64
        || !expected_sha256
            .bytes()
            .all(|byte| byte.is_ascii_digit() || matches!(byte, b'a'..=b'f'))
        || bundle_sha256(bundle)? != expected_sha256
    {
        return Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "prepared bundle hash is invalid",
        ));
    }
    let path = validate_backup_destination(path_str)?;
    let bytes = serde_json::to_vec(bundle).map_err(|_| {
        DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup bundle cannot be serialized",
        )
    })?;
    if bytes.len() as u64 > STUDY_BUNDLE_FILE_MAX_BYTES {
        return Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup bundle exceeds 24 MiB",
        ));
    }
    let file_name = path
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("study-backup.json");
    let temp_path = path.with_file_name(format!(".{file_name}.{}.tmp", Uuid::new_v4().simple()));
    let result = (|| -> std::io::Result<()> {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temp_path)?;
        write_bytes(&mut file, &bytes)?;
        file.flush()?;
        file.sync_all()?;
        drop(file);
        std::fs::rename(&temp_path, &path)?;
        after_replace(&path)?;
        Ok(())
    })();
    if result.is_err() {
        let _ = std::fs::remove_file(&temp_path);
        return Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup file could not be written safely",
        ));
    }
    let readback = read_study_import_file(path_str).map_err(|_| {
        DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup readback validation failed",
        )
    })?;
    if bundle_sha256(&readback)? != expected_sha256 {
        return Err(DeskBridgeError::invalid(
            "study_downgrade_backup_failed",
            "backup readback hash mismatch",
        ));
    }
    Ok(())
}

fn write_verified_backup(
    path_str: &str,
    bundle: &Value,
    expected_sha256: &str,
) -> Result<(), DeskBridgeError> {
    write_verified_backup_with_hooks(
        path_str,
        bundle,
        expected_sha256,
        |file, bytes| file.write_all(bytes),
        |_| Ok(()),
    )
}

#[tauri::command]
pub async fn cmd_study_prepare_downgrade(
    app: AppHandle,
    path_str: String,
) -> Result<Value, DeskBridgeError> {
    let prepared = crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/data/prepare-downgrade",
        Some(json!({})),
    )
    .await?;
    let bundle = prepared.get("bundle").cloned().ok_or_else(|| {
        DeskBridgeError::new(
            None,
            "study_downgrade_backup_failed",
            "prepare response omitted bundle",
        )
    })?;
    let expected_sha256 = prepared
        .get("bundle_sha256")
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| {
            DeskBridgeError::new(
                None,
                "study_downgrade_backup_failed",
                "prepare response omitted bundle hash",
            )
        })?;
    let write_path = path_str.clone();
    let write_hash = expected_sha256.clone();
    tauri::async_runtime::spawn_blocking(move || {
        write_verified_backup(&write_path, &bundle, &write_hash)
    })
    .await
    .map_err(|_| {
        DeskBridgeError::new(
            None,
            "study_downgrade_backup_failed",
            "backup writer did not complete",
        )
    })??;

    let committed = crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        "/api/desk/study/data/prepare-downgrade/commit",
        Some(json!({"bundle_sha256": expected_sha256})),
    )
    .await?;
    Ok(json!({
        "path": path_str,
        "bundleSha256": expected_sha256,
        "committed": committed,
    }))
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
    item_ids: Option<Vec<String>>,
) -> Result<Value, DeskBridgeError> {
    validate_structured_id(&space_id)?;
    validate_structured_id(&artifact_id)?;
    validate_quiz_item_ids(item_ids.as_deref())?;
    crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/quizzes/{artifact_id}/submit"),
        Some(quiz_submit_body(space_id, responses, item_ids)),
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
    fn quiz_item_ids_reject_empty_and_duplicate_lists() {
        assert!(validate_quiz_item_ids(None).is_ok());
        assert!(validate_quiz_item_ids(Some(&[])).is_err());
        let valid = vec!["question-1".to_string(), "question-2".to_string()];
        assert!(validate_quiz_item_ids(Some(&valid)).is_ok());
        let duplicate = vec!["question-1".to_string(), "question-1".to_string()];
        let error = validate_quiz_item_ids(Some(&duplicate)).unwrap_err();
        assert_eq!(error.status, Some(400));
        assert_eq!(error.code, "study_invalid_request");
    }

    #[test]
    fn quiz_submit_body_omits_default_subset_and_serializes_explicit_ids() {
        let full = quiz_submit_body("space-1".to_string(), json!({"q": {}}), None);
        assert!(full.get("item_ids").is_none());

        let subset = quiz_submit_body(
            "space-1".to_string(),
            json!({"q": {}}),
            Some(vec!["question-1".to_string()]),
        );
        assert_eq!(subset["item_ids"], json!(["question-1"]));
    }

    #[test]
    fn study_import_file_accepts_v1_and_v2_json_objects() {
        let root = import_test_root("valid-version");
        for version in [1, 2] {
            let valid = root.join(format!("backup-v{version}.json"));
            std::fs::write(&valid, format!(r#"{{"version":{version}}}"#)).unwrap();
            assert!(read_study_import_file(&valid.display().to_string()).is_ok());
        }

        let invalid_version = root.join("invalid.json");
        std::fs::write(&invalid_version, r#"{"version":3}"#).unwrap();
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
            .set_len(STUDY_BUNDLE_FILE_MAX_BYTES + 1)
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

    #[test]
    fn study_import_file_accepts_legacy_16_mib_and_near_24_mib_v2() {
        let root = import_test_root("bundle-boundaries");
        let legacy = root.join("legacy.json");
        let legacy_padding = "x".repeat(12 * 1024 * 1024);
        std::fs::write(
            &legacy,
            serde_json::to_vec(&json!({"version": 1, "padding": legacy_padding})).unwrap(),
        )
        .unwrap();
        assert!(read_study_import_file(&legacy.display().to_string()).is_ok());

        let v2 = root.join("v2.json");
        let v2_padding = "x".repeat(STUDY_BUNDLE_FILE_MAX_BYTES as usize - 256);
        std::fs::write(
            &v2,
            serde_json::to_vec(&json!({"version": 2, "padding": v2_padding})).unwrap(),
        )
        .unwrap();
        assert!(read_study_import_file(&v2.display().to_string()).is_ok());
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn study_import_rejects_symlink_or_non_file() {
        let root = import_test_root("symlink-nonfile");
        assert_invalid_import_file(read_study_import_file(&root.display().to_string()));

        let target = root.join("target.json");
        let link = root.join("link.json");
        std::fs::write(&target, r#"{"version":2}"#).unwrap();
        #[cfg(unix)]
        {
            std::os::unix::fs::symlink(&target, &link).unwrap();
            assert_invalid_import_file(read_study_import_file(&link.display().to_string()));
        }
        #[cfg(windows)]
        {
            if std::os::windows::fs::symlink_file(&target, &link).is_ok() {
                assert_invalid_import_file(read_study_import_file(&link.display().to_string()));
            }
        }
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn verified_backup_atomically_replaces_and_round_trips_hash() {
        let root = import_test_root("safe-replace");
        let path = root.join("backup.json");
        std::fs::write(&path, r#"{"version":1}"#).unwrap();
        let bundle = json!({"version": 2, "manifest": {"schema_version": 1}});
        let hash = bundle_sha256(&bundle).unwrap();
        write_verified_backup(&path.display().to_string(), &bundle, &hash).unwrap();
        assert_eq!(
            read_study_import_file(&path.display().to_string()).unwrap(),
            bundle
        );
        assert_eq!(bundle_sha256(&bundle).unwrap(), hash);
        assert_eq!(
            std::fs::read_dir(&root)
                .unwrap()
                .filter_map(Result::ok)
                .count(),
            1
        );
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn bundle_hash_matches_the_python_canonical_json_vector() {
        let bundle = json!({
            "version": 2,
            "learning_v1": {
                "version": 1,
                "spaces": [{"title": "数学", "space_id": "s.1"}],
            },
            "tutor_runtime": {"schema_version": 1, "runs": []},
            "manifest": {"schema_version": 1},
        });
        assert_eq!(
            bundle_sha256(&bundle).unwrap(),
            "29bbb599d6ecc59132d4b5372d39f8b81a139f3d262f487ffe4d0b91d6acf5fd"
        );
    }

    #[test]
    fn shared_python_rust_canonical_fixtures_match() {
        let fixture: Value = serde_json::from_str(include_str!(
            "../../hermes_core/tests/fixtures/tutor_canonical_json_vectors.json"
        ))
        .unwrap();
        for vector in fixture["equivalent_pairs"].as_array().unwrap() {
            let expected = vector["sha256"].as_str().unwrap();
            assert_eq!(bundle_sha256(&vector["left"]).unwrap(), expected);
            assert_eq!(bundle_sha256(&vector["right"]).unwrap(), expected);
        }
        for vector in fixture["canonical_values"].as_array().unwrap() {
            assert_eq!(
                bundle_sha256(&vector["value"]).unwrap(),
                vector["sha256"].as_str().unwrap()
            );
        }
        let collision = &fixture["normalized_key_collision"];
        assert!(bundle_sha256(collision).is_err());
    }

    #[test]
    fn unicode_bundle_v2_writes_reads_and_hashes_canonically() {
        let fixture: Value = serde_json::from_str(include_str!(
            "../../hermes_core/tests/fixtures/tutor_canonical_json_vectors.json"
        ))
        .unwrap();
        let root = import_test_root("unicode-canonical");
        let path = root.join("backup.json");
        let bundle = json!({
            "version": 2,
            "payload": fixture["canonical_values"][0]["value"].clone(),
            "decomposed": fixture["equivalent_pairs"][0]["right"].clone(),
        });
        let hash = bundle_sha256(&bundle).unwrap();
        write_verified_backup(&path.display().to_string(), &bundle, &hash).unwrap();
        let readback = read_study_import_file(&path.display().to_string()).unwrap();
        assert_eq!(bundle_sha256(&readback).unwrap(), hash);
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn backup_hash_drift_and_invalid_destination_fail_before_commit() {
        let root = import_test_root("hash-drift");
        let path = root.join("backup.json");
        let bundle = json!({"version": 2});
        let mut commit_called = false;
        let result = write_verified_backup(&path.display().to_string(), &bundle, &"0".repeat(64));
        if result.is_ok() {
            commit_called = true;
        }
        assert!(result.is_err());
        assert!(!commit_called);
        assert!(!path.exists());

        let directory_target = root.join("directory.json");
        std::fs::create_dir(&directory_target).unwrap();
        assert!(write_verified_backup(
            &directory_target.display().to_string(),
            &bundle,
            &bundle_sha256(&bundle).unwrap(),
        )
        .is_err());
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn backup_write_and_readback_failures_do_not_reach_commit() {
        let root = import_test_root("failure-ordering");
        let bundle = json!({"version": 2, "payload": "safe"});
        let hash = bundle_sha256(&bundle).unwrap();

        let write_path = root.join("write-failure.json");
        let mut write_commit_called = false;
        let write_result = write_verified_backup_with_hooks(
            &write_path.display().to_string(),
            &bundle,
            &hash,
            |_, _| Err(std::io::Error::other("injected write failure")),
            |_| Ok(()),
        );
        if write_result.is_ok() {
            write_commit_called = true;
        }
        assert!(write_result.is_err());
        assert!(!write_commit_called);
        assert!(!write_path.exists());

        let readback_path = root.join("readback-failure.json");
        let mut readback_commit_called = false;
        let readback_result = write_verified_backup_with_hooks(
            &readback_path.display().to_string(),
            &bundle,
            &hash,
            |file, bytes| file.write_all(bytes),
            |path| std::fs::write(path, r#"{"version":2,"payload":"corrupt"}"#),
        );
        if readback_result.is_ok() {
            readback_commit_called = true;
        }
        assert!(readback_result.is_err());
        assert!(!readback_commit_called);
        let _ = std::fs::remove_dir_all(&root);
    }
}
