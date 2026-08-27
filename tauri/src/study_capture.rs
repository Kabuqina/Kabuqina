// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Windows-facing Study image intake and trusted desk API proxy commands.
//!
//! The renderer may hold a native-dialog path or camera bytes, but it never
//! receives the app-data path used by the Python capture pipeline. All image
//! inputs are authenticated by their bytes rather than their extension.

use crate::chat::DeskBridgeError;
use image::ImageFormat;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::fs::{File, OpenOptions};
use std::io::{Cursor, Read, Write};
use std::path::{Component, Path, PathBuf};
use tauri::AppHandle;
use uuid::Uuid;

const CAPTURE_SCHEMA_VERSION: u8 = 1;
const CAPTURE_MAX_BYTES: u64 = 20 * 1024 * 1024;
const CAPTURE_MAX_EDGE: u32 = 12_000;
const CAPTURE_MAX_PIXELS: u64 = 50_000_000;
const CAPTURE_PROXY_BODY_MAX_BYTES: usize = 64 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SupportedImage {
    Jpeg,
    Png,
    Webp,
}

impl SupportedImage {
    fn mime(self) -> &'static str {
        match self {
            Self::Jpeg => "image/jpeg",
            Self::Png => "image/png",
            Self::Webp => "image/webp",
        }
    }

    fn extension(self) -> &'static str {
        match self {
            Self::Jpeg => "jpg",
            Self::Png => "png",
            Self::Webp => "webp",
        }
    }

    fn image_format(self) -> ImageFormat {
        match self {
            Self::Jpeg => ImageFormat::Jpeg,
            Self::Png => ImageFormat::Png,
            Self::Webp => ImageFormat::WebP,
        }
    }

    fn extension_matches(self, extension: &str) -> bool {
        match self {
            Self::Jpeg => matches!(extension, "jpg" | "jpeg"),
            Self::Png => extension == "png",
            Self::Webp => extension == "webp",
        }
    }
}

#[derive(Debug, Clone)]
struct StagedImage {
    path: PathBuf,
    mime_type: &'static str,
    sha256: String,
    width: u32,
    height: u32,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CaptureCropV1 {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct CaptureTransformV1 {
    pub schema_version: u8,
    pub capture_id: String,
    pub expected_revision: u64,
    pub crop: CaptureCropV1,
    pub rotation: u16,
    pub grayscale: bool,
    pub max_edge: u32,
}

fn capture_error(code: &str, detail: &str) -> DeskBridgeError {
    DeskBridgeError::invalid(code, detail)
}

fn validate_wire_id(value: &str, label: &str) -> Result<(), DeskBridgeError> {
    let valid = !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_' | b':' | b'.'));
    if valid {
        Ok(())
    } else {
        Err(capture_error(
            "capture_invalid_image",
            &format!("invalid {label}"),
        ))
    }
}

fn validate_purpose(purpose: &str) -> Result<(), DeskBridgeError> {
    if matches!(purpose, "stuck" | "review" | "printed_source") {
        Ok(())
    } else {
        Err(capture_error(
            "capture_invalid_image",
            "invalid capture purpose",
        ))
    }
}

fn detect_image(bytes: &[u8]) -> Result<SupportedImage, DeskBridgeError> {
    if bytes.len() >= 8 && bytes[..8] == [137, 80, 78, 71, 13, 10, 26, 10] {
        return Ok(SupportedImage::Png);
    }
    if bytes.len() >= 3 && bytes[..3] == [0xff, 0xd8, 0xff] {
        return Ok(SupportedImage::Jpeg);
    }
    if bytes.len() >= 12 && &bytes[..4] == b"RIFF" && &bytes[8..12] == b"WEBP" {
        return Ok(SupportedImage::Webp);
    }
    Err(capture_error(
        "capture_invalid_image",
        "only JPEG, PNG, and WebP images are accepted",
    ))
}

fn inspect_image(bytes: &[u8]) -> Result<(SupportedImage, u32, u32), DeskBridgeError> {
    if bytes.is_empty() {
        return Err(capture_error("capture_invalid_image", "image is empty"));
    }
    if bytes.len() as u64 > CAPTURE_MAX_BYTES {
        return Err(capture_error(
            "capture_too_large",
            "image exceeds the 20 MiB capture limit",
        ));
    }
    let kind = detect_image(bytes)?;
    let reader = image::ImageReader::with_format(Cursor::new(bytes), kind.image_format());
    let (width, height) = reader.into_dimensions().map_err(|_| {
        capture_error(
            "capture_invalid_image",
            "image bytes are corrupt or unsupported",
        )
    })?;
    let pixels = u64::from(width).saturating_mul(u64::from(height));
    if width == 0 || height == 0 {
        return Err(capture_error(
            "capture_invalid_image",
            "image dimensions are invalid",
        ));
    }
    if width > CAPTURE_MAX_EDGE || height > CAPTURE_MAX_EDGE || pixels > CAPTURE_MAX_PIXELS {
        return Err(capture_error(
            "capture_too_large",
            "image dimensions exceed the safe capture limit",
        ));
    }
    Ok((kind, width, height))
}

fn capture_root(data_dir: &Path) -> PathBuf {
    data_dir.join("study-captures")
}

fn temp_capture_dir(data_dir: &Path, capture_id: &str) -> PathBuf {
    capture_root(data_dir).join("temp").join(capture_id)
}

fn path_has_parent_component(path: &Path) -> bool {
    path.components()
        .any(|component| matches!(component, Component::ParentDir))
}

fn canonical_upload_source(path: &Path, data_dir: &Path) -> Result<PathBuf, DeskBridgeError> {
    if !path.is_absolute() || path_has_parent_component(path) {
        return Err(capture_error(
            "capture_invalid_image",
            "upload path must be an absolute native-dialog selection",
        ));
    }
    let canonical = std::fs::canonicalize(path)
        .map_err(|_| capture_error("capture_invalid_image", "selected image is unavailable"))?;
    let metadata = std::fs::metadata(&canonical)
        .map_err(|_| capture_error("capture_invalid_image", "selected image is unavailable"))?;
    if !metadata.is_file() {
        return Err(capture_error(
            "capture_invalid_image",
            "selected path is not a regular file",
        ));
    }
    if metadata.len() > CAPTURE_MAX_BYTES {
        return Err(capture_error(
            "capture_too_large",
            "image exceeds the 20 MiB capture limit",
        ));
    }

    // A renderer must never use the upload seam to read back temporary or
    // confirmed media managed by the desktop/Python pipeline.
    let canonical_capture_root =
        std::fs::canonicalize(capture_root(data_dir)).unwrap_or_else(|_| capture_root(data_dir));
    if canonical.starts_with(&canonical_capture_root) {
        return Err(capture_error(
            "capture_invalid_image",
            "managed capture media cannot be selected as a new upload",
        ));
    }
    Ok(canonical)
}

fn read_upload(path: &Path, data_dir: &Path) -> Result<Vec<u8>, DeskBridgeError> {
    let canonical = canonical_upload_source(path, data_dir)?;
    let mut file = File::open(&canonical).map_err(|_| {
        capture_error(
            "capture_invalid_image",
            "selected image could not be opened",
        )
    })?;
    let mut bytes = Vec::new();
    std::io::Read::by_ref(&mut file)
        .take(CAPTURE_MAX_BYTES + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| capture_error("capture_invalid_image", "selected image could not be read"))?;
    if bytes.len() as u64 > CAPTURE_MAX_BYTES {
        return Err(capture_error(
            "capture_too_large",
            "image exceeds the 20 MiB capture limit",
        ));
    }
    let (kind, _, _) = inspect_image(&bytes)?;
    let extension = canonical
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    if !kind.extension_matches(&extension) {
        return Err(capture_error(
            "capture_invalid_image",
            "image extension does not match its content",
        ));
    }
    Ok(bytes)
}

fn atomic_stage_bytes(
    data_dir: &Path,
    capture_id: &str,
    bytes: &[u8],
) -> Result<StagedImage, DeskBridgeError> {
    validate_wire_id(capture_id, "capture_id")?;
    let (kind, width, height) = inspect_image(bytes)?;
    let sha256 = hex::encode(Sha256::digest(bytes));
    let directory = temp_capture_dir(data_dir, capture_id);
    std::fs::create_dir_all(&directory).map_err(|_| {
        DeskBridgeError::new(
            None,
            "capture_invalid_image",
            "temporary capture directory is unavailable",
        )
    })?;
    let destination = directory.join(format!("original.{}", kind.extension()));

    if destination.exists() {
        let existing = std::fs::read(&destination).map_err(|_| {
            DeskBridgeError::new(
                None,
                "capture_invalid_image",
                "existing temporary capture is unavailable",
            )
        })?;
        if Sha256::digest(&existing).as_slice() != Sha256::digest(bytes).as_slice() {
            return Err(capture_error(
                "capture_revision_conflict",
                "capture_id already refers to different image bytes",
            ));
        }
        return Ok(StagedImage {
            path: destination,
            mime_type: kind.mime(),
            sha256,
            width,
            height,
        });
    }

    let part = directory.join(format!(".incoming-{}", Uuid::new_v4()));
    let write_result = (|| -> std::io::Result<()> {
        let mut file = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&part)?;
        file.write_all(bytes)?;
        file.sync_all()?;
        std::fs::rename(&part, &destination)?;
        Ok(())
    })();
    if write_result.is_err() {
        let _ = std::fs::remove_file(&part);
        return Err(DeskBridgeError::new(
            None,
            "capture_invalid_image",
            "image could not be staged",
        ));
    }

    Ok(StagedImage {
        path: destination,
        mime_type: kind.mime(),
        sha256,
        width,
        height,
    })
}

fn validate_transform(transform: &CaptureTransformV1) -> Result<(), DeskBridgeError> {
    if transform.schema_version != CAPTURE_SCHEMA_VERSION {
        return Err(capture_error(
            "capture_invalid_image",
            "unsupported capture transform schema",
        ));
    }
    validate_wire_id(&transform.capture_id, "capture_id")?;
    if transform.expected_revision == 0 {
        return Err(capture_error(
            "capture_revision_conflict",
            "expected_revision must be positive",
        ));
    }
    if !matches!(transform.rotation, 0 | 90 | 180 | 270) {
        return Err(capture_error(
            "capture_invalid_image",
            "rotation must be 0, 90, 180, or 270",
        ));
    }
    if !(256..=4096).contains(&transform.max_edge) {
        return Err(capture_error(
            "capture_invalid_image",
            "max_edge must be within 256..4096",
        ));
    }
    let crop = &transform.crop;
    let values = [crop.x, crop.y, crop.width, crop.height];
    if values.iter().any(|value| !value.is_finite())
        || crop.x < 0.0
        || crop.y < 0.0
        || crop.width <= 0.0
        || crop.height <= 0.0
        || crop.x + crop.width > 1.0 + f64::EPSILON
        || crop.y + crop.height > 1.0 + f64::EPSILON
    {
        return Err(capture_error(
            "capture_invalid_image",
            "crop must stay within normalized 0..1 coordinates",
        ));
    }
    Ok(())
}

fn validate_proxy_body(body: &Value) -> Result<(), DeskBridgeError> {
    if !body.is_object() {
        return Err(capture_error(
            "capture_invalid_image",
            "capture request body must be an object",
        ));
    }
    let size = serde_json::to_vec(body)
        .map_err(|_| capture_error("capture_invalid_image", "capture request is invalid"))?
        .len();
    if size > CAPTURE_PROXY_BODY_MAX_BYTES {
        return Err(capture_error(
            "capture_too_large",
            "capture request metadata is too large",
        ));
    }
    Ok(())
}

fn contains_private_path_field(value: &Value) -> bool {
    match value {
        Value::Object(map) => map.iter().any(|(key, value)| {
            matches!(
                key.as_str(),
                "path"
                    | "staged_path"
                    | "managed_path"
                    | "absolute_path"
                    | "source_path"
                    | "original_path"
                    | "normalized_path"
            ) || contains_private_path_field(value)
        }),
        Value::Array(items) => items.iter().any(contains_private_path_field),
        _ => false,
    }
}

fn renderer_safe_response(value: Value) -> Result<Value, DeskBridgeError> {
    if contains_private_path_field(&value) {
        return Err(DeskBridgeError::new(
            Some(502),
            "desk_invalid_response",
            "capture response exposed a managed path",
        ));
    }
    Ok(value)
}

async fn register_staged_capture(
    app: &AppHandle,
    capture_id: &str,
    space_id: &str,
    purpose: &str,
    source_kind: &str,
    staged: &StagedImage,
) -> Result<Value, DeskBridgeError> {
    let value = crate::chat::desk_json_request_structured(
        app,
        reqwest::Method::POST,
        "/api/desk/study/captures/stage",
        Some(json!({
            "schema_version": CAPTURE_SCHEMA_VERSION,
            "capture_id": capture_id,
            "space_id": space_id,
            "purpose": purpose,
            "source_kind": source_kind,
            "staged_path": staged.path,
            "mime_type": staged.mime_type,
            "sha256": staged.sha256,
            "preview": {"width": staged.width, "height": staged.height},
        })),
    )
    .await?;
    renderer_safe_response(value)
}

#[tauri::command]
pub async fn cmd_study_capture_stage_upload(
    app: AppHandle,
    path: String,
    capture_id: String,
    space_id: String,
    purpose: String,
) -> Result<Value, DeskBridgeError> {
    validate_wire_id(&capture_id, "capture_id")?;
    validate_wire_id(&space_id, "space_id")?;
    validate_purpose(&purpose)?;
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|_| {
        DeskBridgeError::new(None, "capture_invalid_image", "app data is unavailable")
    })?;
    let bytes = read_upload(Path::new(&path), &data_dir)?;
    let staged = atomic_stage_bytes(&data_dir, &capture_id, &bytes)?;
    register_staged_capture(&app, &capture_id, &space_id, &purpose, "upload", &staged).await
}

#[tauri::command]
pub async fn cmd_study_capture_stage_camera(
    app: AppHandle,
    bytes: Vec<u8>,
    capture_id: String,
    space_id: String,
    purpose: String,
) -> Result<Value, DeskBridgeError> {
    validate_wire_id(&capture_id, "capture_id")?;
    validate_wire_id(&space_id, "space_id")?;
    validate_purpose(&purpose)?;
    let data_dir = crate::paths::ensure_data_dir(&app).map_err(|_| {
        DeskBridgeError::new(None, "capture_invalid_image", "app data is unavailable")
    })?;
    let staged = atomic_stage_bytes(&data_dir, &capture_id, &bytes)?;
    register_staged_capture(&app, &capture_id, &space_id, &purpose, "camera", &staged).await
}

#[tauri::command]
pub async fn cmd_study_capture_normalize(
    app: AppHandle,
    transform: CaptureTransformV1,
) -> Result<Value, DeskBridgeError> {
    validate_transform(&transform)?;
    let capture_id = transform.capture_id.clone();
    let body = serde_json::to_value(transform)
        .map_err(|_| capture_error("capture_invalid_image", "capture transform is invalid"))?;
    let value = crate::chat::desk_json_request_structured(
        &app,
        reqwest::Method::POST,
        &format!("/api/desk/study/captures/{capture_id}/normalize"),
        Some(body),
    )
    .await?;
    renderer_safe_response(value)
}

async fn capture_action(
    app: &AppHandle,
    capture_id: &str,
    action: &str,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    validate_wire_id(capture_id, "capture_id")?;
    validate_proxy_body(&body)?;
    let value = crate::chat::desk_json_request_structured(
        app,
        reqwest::Method::POST,
        &format!("/api/desk/study/captures/{capture_id}/{action}"),
        Some(body),
    )
    .await?;
    renderer_safe_response(value)
}

#[tauri::command]
pub async fn cmd_study_capture_transcribe(
    app: AppHandle,
    capture_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    capture_action(&app, &capture_id, "transcribe", body).await
}

#[tauri::command]
pub async fn cmd_study_capture_assistance(
    app: AppHandle,
    capture_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    capture_action(&app, &capture_id, "assistance", body).await
}

#[tauri::command]
pub async fn cmd_study_capture_review(
    app: AppHandle,
    capture_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    capture_action(&app, &capture_id, "review", body).await
}

#[tauri::command]
pub async fn cmd_study_capture_confirm(
    app: AppHandle,
    capture_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    let result = capture_action(&app, &capture_id, "confirm", body).await?;
    if matches!(
        result.get("status").and_then(Value::as_str),
        Some("confirmed" | "abandoned")
    ) {
        if let Ok(data_dir) = crate::paths::ensure_data_dir(&app) {
            let _ = std::fs::remove_dir_all(temp_capture_dir(&data_dir, &capture_id));
        }
    }
    Ok(result)
}

#[tauri::command]
pub async fn cmd_study_capture_abandon(
    app: AppHandle,
    capture_id: String,
    body: Value,
) -> Result<Value, DeskBridgeError> {
    validate_wire_id(&capture_id, "capture_id")?;
    validate_proxy_body(&body)?;
    let result = capture_action(&app, &capture_id, "abandon", body).await;
    if let Ok(data_dir) = crate::paths::ensure_data_dir(&app) {
        let _ = std::fs::remove_dir_all(temp_capture_dir(&data_dir, &capture_id));
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unique_root(label: &str) -> PathBuf {
        std::env::temp_dir().join(format!(
            "kabuqina-study-capture-{}-{label}-{}",
            std::process::id(),
            Uuid::new_v4()
        ))
    }

    fn one_pixel_png() -> Vec<u8> {
        vec![
            137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0, 1, 0, 0, 0, 1,
            8, 6, 0, 0, 0, 31, 21, 196, 137, 0, 0, 0, 13, 73, 68, 65, 84, 8, 29, 99, 248, 207, 192,
            240, 31, 0, 5, 0, 1, 255, 137, 153, 61, 29, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96,
            130,
        ]
    }

    #[test]
    fn camera_staging_accepts_real_png_and_is_idempotent() {
        let root = unique_root("camera");
        let bytes = one_pixel_png();
        let first = atomic_stage_bytes(&root, "capture-1", &bytes).unwrap();
        let second = atomic_stage_bytes(&root, "capture-1", &bytes).unwrap();
        assert_eq!(first.path, second.path);
        assert_eq!(first.mime_type, "image/png");
        assert_eq!((first.width, first.height), (1, 1));
        assert!(first.path.starts_with(temp_capture_dir(&root, "capture-1")));
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn camera_staging_rejects_non_image_and_oversize_payloads() {
        let root = unique_root("invalid");
        let invalid = atomic_stage_bytes(&root, "capture-1", b"not an image").unwrap_err();
        assert_eq!(invalid.code, "capture_invalid_image");
        let oversized = vec![0u8; CAPTURE_MAX_BYTES as usize + 1];
        let error = atomic_stage_bytes(&root, "capture-2", &oversized).unwrap_err();
        assert_eq!(error.code, "capture_too_large");
        assert!(!capture_root(&root).exists());
    }

    #[test]
    fn repeated_capture_id_rejects_different_bytes() {
        let root = unique_root("conflict");
        let bytes = one_pixel_png();
        atomic_stage_bytes(&root, "capture-1", &bytes).unwrap();
        let mut different = bytes;
        different.push(0);
        let error = atomic_stage_bytes(&root, "capture-1", &different).unwrap_err();
        assert_eq!(error.code, "capture_revision_conflict");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn upload_rejects_relative_traversal_and_fake_extension() {
        let root = unique_root("upload");
        std::fs::create_dir_all(&root).unwrap();
        assert!(canonical_upload_source(Path::new("..\\secret.png"), &root).is_err());

        let source = root.with_extension("txt");
        std::fs::write(&source, one_pixel_png()).unwrap();
        let error = read_upload(&source, &root).unwrap_err();
        assert_eq!(error.code, "capture_invalid_image");
        let _ = std::fs::remove_file(source);
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn upload_cannot_restage_managed_capture_media() {
        let root = unique_root("managed");
        let managed = capture_root(&root).join("managed").join("photo.png");
        std::fs::create_dir_all(managed.parent().unwrap()).unwrap();
        std::fs::write(&managed, one_pixel_png()).unwrap();
        let error = read_upload(&managed, &root).unwrap_err();
        assert_eq!(error.code, "capture_invalid_image");
        let _ = std::fs::remove_dir_all(root);
    }

    #[test]
    fn transform_contract_rejects_out_of_bounds_crop_and_rotation() {
        let mut transform = CaptureTransformV1 {
            schema_version: 1,
            capture_id: "capture-1".into(),
            expected_revision: 1,
            crop: CaptureCropV1 {
                x: 0.1,
                y: 0.1,
                width: 0.8,
                height: 0.8,
            },
            rotation: 90,
            grayscale: false,
            max_edge: 1280,
        };
        assert!(validate_transform(&transform).is_ok());
        transform.crop.width = 0.95;
        assert!(validate_transform(&transform).is_err());
        transform.crop.width = 0.8;
        transform.rotation = 45;
        assert!(validate_transform(&transform).is_err());
    }

    #[test]
    fn renderer_response_fails_closed_on_managed_path() {
        let safe = json!({"capture_id": "capture-1", "preview": {"width": 1, "height": 1}});
        assert!(renderer_safe_response(safe).is_ok());
        let unsafe_value = json!({"capture_id": "capture-1", "managed_path": "C:\\secret.png"});
        let error = renderer_safe_response(unsafe_value).unwrap_err();
        assert_eq!(error.code, "desk_invalid_response");
    }
}
