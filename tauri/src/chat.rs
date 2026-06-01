// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Shell → Hermes HTTP proxy (Tauri `invoke` → reqwest to 127.0.0.1).
//!
//! The webview cannot `fetch` Hermes directly (origin + session token). We use
//! `X-HermesDesk-Auth` (shared with `HERMESDESK_BRIDGE_SECRET`) and the same
//! `Authorization: Bearer` as the dashboard: loaded from
//! `hermes_web_session_token.txt` if present, else parsed from
//! `GET /` (``__HERMES_SESSION_TOKEN__`` in ``index.html``) — no bundle step
//! required for the token to exist.

use crate::AppState;
use crate::paths;
use base64::Engine;
use futures_util::StreamExt;
use once_cell::sync::OnceCell;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::path::PathBuf;
use std::time::Duration;
use tauri::AppHandle;
use tauri::Emitter;
use tauri::Manager;
use tokio::sync::Mutex as AsyncMutex;

const HERMES_HTTP_TIMEOUT: Duration = Duration::from_secs(600);
/// Cached ``(port, bearer)`` for the in-process Hermes process.
type BearerEntry = (u16, String);
static HERMES_BEARER_CACHE: OnceCell<AsyncMutex<Option<BearerEntry>>> = OnceCell::new();

fn bearer_cache() -> &'static AsyncMutex<Option<BearerEntry>> {
    HERMES_BEARER_CACHE.get_or_init(|| AsyncMutex::new(None))
}

pub(crate) fn http_client() -> reqwest::Client {
    // Loopback + system HTTP proxy (e.g. Clash) is a common source of 401 / wrong
    // responses; never proxy requests to 127.0.0.1.
    reqwest::Client::builder()
        .no_proxy()
        .timeout(HERMES_HTTP_TIMEOUT)
        .build()
        .expect("reqwest client")
}

async fn desk_json_request(
    app: &AppHandle,
    method: reqwest::Method,
    path: &str,
    body: Option<Value>,
) -> Result<Value, String> {
    let base = hermes_base(app).await?;
    let token = desk_auth_header(app).await?;
    let client = http_client();
    let mut req = client
        .request(method, format!("{base}{path}"))
        .header("X-HermesDesk-Auth", &token);
    if let Some(b) = hermes_bearer_resolved(app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    if let Some(body) = body {
        req = req.header("Content-Type", "application/json").json(&body);
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v = desk_response_json(res).await?;
    if !status.is_success() {
        let err = v
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("request_failed");
        let detail = v.get("detail").and_then(Value::as_str).unwrap_or("");
        return Err(if detail.is_empty() {
            err.to_string()
        } else {
            format!("{err}: {detail}")
        });
    }
    Ok(v)
}

/// Same bearer string the embedded Hermes web UI uses (`web_server._SESSION_TOKEN`).
async fn hermes_bearer_from_data_dir(app: &AppHandle) -> Option<String> {
    let dir = paths::ensure_data_dir(app).ok()?;
    let path = dir.join("hermes_web_session_token.txt");
    for _ in 0u32..20 {
        if let Ok(s) = tokio::fs::read_to_string(&path).await {
            let t = s.trim();
            if !t.is_empty() {
                return Some(t.to_string());
            }
        }
        tokio::time::sleep(Duration::from_millis(50)).await;
    }
    None
}

/// ``Authorization: Bearer`` — same as the open dashboard (must match
/// `web_server._SESSION_TOKEN` for the running process).
pub(crate) async fn hermes_bearer_resolved(app: &AppHandle) -> Option<String> {
    let state: tauri::State<'_, AppState> = app.state();
    let port = *state.hermes_port.lock().await.as_ref()?;
    {
        let c = bearer_cache().lock().await;
        if let Some((p, t)) = c.as_ref() {
            if *p == port {
                return Some(t.clone());
            }
        }
    }
    if let Some(t) = hermes_bearer_from_data_dir(app).await {
        *bearer_cache().lock().await = Some((port, t.clone()));
        return Some(t);
    }
    let base = format!("http://127.0.0.1:{port}");
    let text = match http_client().get(&base).send().await {
        Ok(r) => r.text().await,
        Err(e) => {
            log::warn!("hermes: GET {base} failed: {e}");
            return None;
        }
    };
    let text = match text {
        Ok(t) => t,
        Err(e) => {
            log::warn!("hermes: read index body: {e}");
            return None;
        }
    };
    const NEEDLE: &str = "__HERMES_SESSION_TOKEN__=\"";
    let rest = match text.split_once(NEEDLE) {
        Some((_, r)) => r,
        None => {
            log::warn!(
                "hermes: no session token in index.html (is dashboard built? len={})",
                text.len()
            );
            return None;
        }
    };
    let end = rest.find('"')?;
    let token = rest[..end].to_string();
    if token.is_empty() {
        return None;
    }
    log::info!("hermes: using bearer from index.html (port {port})");
    *bearer_cache().lock().await = Some((port, token.clone()));
    Some(token)
}

pub(crate) async fn hermes_base(app: &AppHandle) -> Result<String, String> {
    let state: tauri::State<'_, AppState> = app.state();
    let port =
        *state.hermes_port.lock().await.as_ref().ok_or_else(|| {
            "Hermes is not ready yet. Wait a few seconds and try again.".to_string()
        })?;
    Ok(format!("http://127.0.0.1:{port}"))
}

pub(crate) async fn desk_auth_header(app: &AppHandle) -> Result<String, String> {
    let state: tauri::State<'_, AppState> = app.state();
    let token = {
        let g = state.desk_auth_token.lock().await;
        g.clone()
    };
    token.ok_or_else(|| "Shell auth not ready.".to_string())
}

/// Read the full HTTP body and parse JSON. Gives a clearer error than
/// ``Response::json()`` when Hermes returns HTML (SPA fallback), an empty
/// body, or a truncated response — all of which surface as the opaque
/// "error decoding response body" from reqwest.
pub(crate) async fn desk_response_json(res: reqwest::Response) -> Result<Value, String> {
    let status = res.status();
    let bytes = res.bytes().await.map_err(|e| {
        format!(
            "Failed to read Hermes response (HTTP {}): {}",
            status.as_u16(),
            e
        )
    })?;
    let mut slice = bytes.as_ref();
    if slice.starts_with(&[0xEF, 0xBB, 0xBF]) {
        slice = &slice[3..];
    }
    if slice.is_empty() {
        return Err(format!(
            "Hermes returned an empty body (HTTP {}). If you just upgraded, rebuild the Python bundle (python/build_bundle.ps1).",
            status.as_u16()
        ));
    }
    serde_json::from_slice(slice).map_err(|e| {
        let head_len = slice.len().min(220);
        let head = String::from_utf8_lossy(&slice[..head_len]);
        let head: String = head.chars().take(180).collect();
        format!(
            "Hermes returned non-JSON (HTTP {}): {} — starts with: {:?}",
            status.as_u16(),
            e,
            head
        )
    })
}

/// One attachment for ``/api/desk/chat-proto`` (base64 payload; matches Hermes `web_server`).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeskChatAttachment {
    pub name: String,
    pub mime: String,
    pub data: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct ChatStreamEnvelope {
    request_id: String,
    event: Value,
}

fn prepare_desk_chat_body(
    app: &AppHandle,
    message: &str,
    session_id: Option<&String>,
    attachments: Option<&Vec<DeskChatAttachment>>,
) -> Result<Value, String> {
    let py_attachments: Option<Vec<Value>> = if let Some(atts) = attachments {
        let workspace = paths::ensure_workspace(app).map_err(|e| format!("workspace: {}", e))?;
        let sid = session_id.map(String::as_str).unwrap_or("_new");
        let safe_sid = sid.replace(|c: char| !c.is_alphanumeric() && c != '_' && c != '-', "_");
        let upload_dir: PathBuf = workspace.join(".hermesdesk_uploads").join(&safe_sid);
        std::fs::create_dir_all(&upload_dir).map_err(|e| format!("mkdir uploads: {}", e))?;

        let mut out: Vec<Value> = Vec::with_capacity(atts.len());
        for a in atts {
            let raw = match base64::engine::general_purpose::STANDARD.decode(&a.data) {
                Ok(b) => b,
                Err(e) => {
                    log::warn!("base64 decode failed for {}: {}", a.name, e);
                    continue;
                }
            };
            let dest = upload_dir.join(&a.name);
            if let Err(e) = std::fs::write(&dest, &raw) {
                log::warn!("write attachment {}: {}", a.name, e);
                continue;
            }
            let path = dest.to_string_lossy().into_owned();
            log::info!("attachment saved: {} -> {}", a.name, path);

            let is_image_or_text = a.mime.starts_with("image/")
                || a.mime.starts_with("text/")
                || matches!(a.mime.as_str(), "application/json" | "application/xml");

            if is_image_or_text {
                out.push(serde_json::json!({
                    "name": a.name,
                    "mime": a.mime,
                    "data": a.data,
                    "path": path,
                }));
            } else {
                out.push(serde_json::json!({
                    "name": a.name,
                    "mime": a.mime,
                    "path": path,
                }));
            }
        }
        if out.is_empty() { None } else { Some(out) }
    } else {
        None
    };

    Ok(serde_json::json!({
        "message": message,
        "session_id": session_id,
        "attachments": py_attachments,
    }))
}

/// POST /api/desk/chat-proto — full JSON body from Hermes.
#[tauri::command]
pub async fn cmd_chat_send(
    app: AppHandle,
    message: String,
    session_id: Option<String>,
    attachments: Option<Vec<DeskChatAttachment>>,
) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = prepare_desk_chat_body(&app, &message, session_id.as_ref(), attachments.as_ref())?;
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/chat-proto"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if status.as_u16() == 503 {
        if v.get("status").and_then(Value::as_str) == Some("warming") {
            return Err("desk_warming".into());
        }
    }
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

/// POST /api/desk/chat-stream — emits SSE events to the webview while running.
#[tauri::command]
pub async fn cmd_chat_send_stream(
    app: AppHandle,
    request_id: String,
    message: String,
    session_id: Option<String>,
    attachments: Option<Vec<DeskChatAttachment>>,
) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = prepare_desk_chat_body(&app, &message, session_id.as_ref(), attachments.as_ref())?;
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/chat-stream"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    if !status.is_success() {
        let text = res.text().await.unwrap_or_else(|e| e.to_string());
        if status.as_u16() == 503 && text.contains("warming") {
            return Err("desk_warming".into());
        }
        return Err(text);
    }

    let mut stream = res.bytes_stream();
    let mut buffer = String::new();
    let mut final_event: Option<Value> = None;
    let mut error_event: Option<Value> = None;

    while let Some(chunk) = stream.next().await {
        let bytes = chunk.map_err(|e| e.to_string())?;
        let text = String::from_utf8_lossy(&bytes).replace("\r\n", "\n");
        buffer.push_str(&text);
        while let Some(idx) = buffer.find("\n\n") {
            let frame = buffer[..idx].to_string();
            buffer.drain(..idx + 2);

            let mut data = String::new();
            for line in frame.lines() {
                if let Some(rest) = line.strip_prefix("data:") {
                    if !data.is_empty() {
                        data.push('\n');
                    }
                    data.push_str(rest.trim_start());
                }
            }
            let data = data.trim();
            if data.is_empty() {
                continue;
            }
            let event: Value = match serde_json::from_str(data) {
                Ok(v) => v,
                Err(e) => {
                    if final_event.is_some() {
                        log::warn!("desk stream: ignoring malformed SSE after final: {e}");
                        continue;
                    }
                    return Err(e.to_string());
                }
            };
            let _ = app.emit(
                "chat-stream-event",
                ChatStreamEnvelope {
                    request_id: request_id.clone(),
                    event: event.clone(),
                },
            );
            match event.get("type").and_then(Value::as_str) {
                Some("final") => final_event = Some(event),
                Some("error") => error_event = Some(event),
                _ => {}
            }
        }
    }

    if let Some(v) = final_event {
        return Ok(v);
    }
    if let Some(v) = error_event {
        return Ok(v);
    }
    Ok(serde_json::json!({
        "ok": false,
        "error": "stream_closed",
        "detail": "Stream closed before a final response.",
    }))
}

/// GET /api/desk/chat-preview/{session_id} — lightweight agent progress poll.
#[tauri::command]
pub async fn cmd_chat_preview(
    app: AppHandle,
    session_id: String,
    since: Option<u64>,
) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let client = http_client();
    let url = format!(
        "{base}/api/desk/chat-preview/{session_id}?since={}",
        since.unwrap_or(0)
    );
    let mut req = client.get(&url).header("X-HermesDesk-Auth", &token);
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

/// POST /api/desk/stop — interrupt in-flight agent for this session.
#[tauri::command]
pub async fn cmd_desk_stop(app: AppHandle, session_id: String) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = serde_json::json!({ "session_id": session_id });
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/stop"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

/// POST /api/desk/interaction-response — resume a blocked agent interaction.
#[tauri::command]
pub async fn cmd_interaction_response(
    app: AppHandle,
    session_id: String,
    interaction_id: String,
    action: String,
    text: Option<String>,
    data: Option<Value>,
) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = serde_json::json!({
        "session_id": session_id,
        "interaction_id": interaction_id,
        "action": action,
        "text": text.unwrap_or_default(),
        "data": data.unwrap_or_else(|| serde_json::json!({})),
    });
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/interaction-response"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

/// GET /api/sessions?source=cli (desktop shell only sees its own sessions)
#[tauri::command]
pub async fn cmd_get_sessions(
    app: AppHandle,
    limit: Option<u32>,
    offset: Option<u32>,
    source: Option<String>,
) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let lim = limit.unwrap_or(50);
    let off = offset.unwrap_or(0);
    let mut url = format!("{base}/api/sessions?limit={lim}&offset={off}");
    if let Some(ref src) = source {
        // source values are always simple ASCII platform keys (cli, weixin, etc.)
        url.push_str(&format!("&source={}", src));
    }
    let client = http_client();
    let mut req = client.get(&url).header("X-HermesDesk-Auth", &token);
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

/// GET /api/sessions/{id}/messages
#[tauri::command]
pub async fn cmd_get_session_messages(app: AppHandle, id: String) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let url = format!("{base}/api/sessions/{id}/messages");
    let client = http_client();
    let mut req = client.get(&url).header("X-HermesDesk-Auth", &token);
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

/// POST /api/desk/transcribe — proxy audio base64 to the Python STT endpoint.
///
/// Rust receives the raw base64 string from the webview, forwards it as JSON
/// to the Python process (which writes the temp file and runs the STT call),
/// and returns the recognised text string on success.
#[tauri::command]
pub async fn cmd_transcribe(
    app: AppHandle,
    audio_b64: String,
    mime: String,
) -> Result<String, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = serde_json::json!({
        "audio_b64": audio_b64,
        "mime": mime,
    });
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/transcribe"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        let err = v
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("transcription_failed");
        let detail = v.get("detail").and_then(Value::as_str).unwrap_or("");
        return Err(if detail.is_empty() {
            err.to_string()
        } else {
            format!("{err}: {detail}")
        });
    }
    v.get("transcript")
        .and_then(Value::as_str)
        .map(str::to_string)
        .ok_or_else(|| "no transcript in response".to_string())
}

/// POST /api/desk/save-voice-setup — persist STT/TTS provider + secrets from
/// the desktop wizard. The Python side writes `.env` and `config.yaml` and
/// updates `os.environ` so the next call (e.g. STT) picks up the new key
/// without an app restart.
#[tauri::command]
pub async fn cmd_save_voice_setup(
    app: AppHandle,
    section: String,
    provider: Option<String>,
    env: HashMap<String, String>,
) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = serde_json::json!({
        "section": section,
        "provider": provider,
        "env": env,
    });
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/save-voice-setup"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        let err = v
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("save_failed");
        let detail = v.get("detail").and_then(Value::as_str).unwrap_or("");
        return Err(if detail.is_empty() {
            err.to_string()
        } else {
            format!("{err}: {detail}")
        });
    }
    Ok(v)
}

/// POST /api/desk/tts — generate TTS audio for the given text.
///
/// Returns the audio bytes as a base64-encoded string so the webview
/// can create a Blob URL and play it directly.
#[tauri::command]
pub async fn cmd_tts_speak(app: AppHandle, text: String) -> Result<String, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let body = serde_json::json!({"text": text});
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/tts"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json");
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.json(&body).send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    if !status.is_success() {
        let text_body = res.text().await.unwrap_or_else(|e| e.to_string());
        return Err(text_body);
    }
    let bytes = res.bytes().await.map_err(|e| e.to_string())?;
    Ok(base64::engine::general_purpose::STANDARD.encode(&bytes))
}

/// GET /api/desk/stt-model/status — is the local STT GGML model already on disk?
///
/// Returns the raw JSON ``{ "downloaded": bool, "size": int, "path": str }``
/// so the renderer can decide whether to show the first-time download
/// prompt before recording.
#[tauri::command]
pub async fn cmd_stt_model_status(app: AppHandle) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let client = http_client();
    let mut req = client
        .get(format!("{base}/api/desk/stt-model/status"))
        .header("X-HermesDesk-Auth", &token);
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v = desk_response_json(res).await?;
    if !status.is_success() {
        let err = v
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("status_failed");
        let detail = v.get("detail").and_then(Value::as_str).unwrap_or("");
        return Err(if detail.is_empty() {
            err.to_string()
        } else {
            format!("{err}: {detail}")
        });
    }
    Ok(v)
}

/// POST /api/desk/stt-model/download — fetch the GGML model on demand.
///
/// Blocking on the Python side (streams ~57 MB); the reqwest call here
/// inherits the long ``HERMES_HTTP_TIMEOUT`` so a slow connection still
/// finishes.
#[tauri::command]
pub async fn cmd_stt_model_download(app: AppHandle) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let client = http_client();
    let mut req = client
        .post(format!("{base}/api/desk/stt-model/download"))
        .header("X-HermesDesk-Auth", &token)
        .header("Content-Type", "application/json")
        // Some stacks wait for a JSON body when Content-Type is
        // application/json; send an explicit empty object.
        .json(&serde_json::json!({}));
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v = desk_response_json(res).await?;
    if !status.is_success() {
        let err = v
            .get("error")
            .and_then(Value::as_str)
            .unwrap_or("download_failed");
        let detail = v.get("detail").and_then(Value::as_str).unwrap_or("");
        return Err(if detail.is_empty() {
            err.to_string()
        } else {
            format!("{err}: {detail}")
        });
    }
    Ok(v)
}

/// GET /api/desk/load-packages — list optional large assets managed on demand.
#[tauri::command]
pub async fn cmd_load_packages(app: AppHandle) -> Result<Value, String> {
    desk_json_request(&app, reqwest::Method::GET, "/api/desk/load-packages", None).await
}

/// POST /api/desk/load-packages/{id}/download — download one optional package.
#[tauri::command]
pub async fn cmd_load_package_download(
    app: AppHandle,
    package_id: String,
) -> Result<Value, String> {
    let path = format!("/api/desk/load-packages/{package_id}/download");
    desk_json_request(
        &app,
        reqwest::Method::POST,
        &path,
        Some(serde_json::json!({})),
    )
    .await
}

/// DELETE /api/desk/load-packages/{id} — remove one optional package.
#[tauri::command]
pub async fn cmd_load_package_delete(app: AppHandle, package_id: String) -> Result<Value, String> {
    let path = format!("/api/desk/load-packages/{package_id}");
    desk_json_request(&app, reqwest::Method::DELETE, &path, None).await
}

/// DELETE /api/sessions/{id}
#[tauri::command]
pub async fn cmd_delete_session(app: AppHandle, id: String) -> Result<Value, String> {
    let base = hermes_base(&app).await?;
    let token = desk_auth_header(&app).await?;
    let url = format!("{base}/api/sessions/{id}");
    let client = http_client();
    let mut req = client.delete(&url).header("X-HermesDesk-Auth", &token);
    if let Some(b) = hermes_bearer_resolved(&app).await {
        req = req.header("Authorization", format!("Bearer {b}"));
    }
    let res = req.send().await.map_err(|e| e.to_string())?;
    let status = res.status();
    let v: Value = res.json().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(v.to_string());
    }
    Ok(v)
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HermesDeskBootState {
    pub port: Option<u16>,
    pub warming: bool,
}

/// Port + desk-minimal warm state for the shell boot UI.
#[tauri::command]
pub async fn cmd_get_hermes_desk_boot_state(app: AppHandle) -> Result<HermesDeskBootState, String> {
    let state: tauri::State<AppState> = app.state();
    let port = *state.hermes_port.lock().await;
    let Some(port) = port else {
        return Ok(HermesDeskBootState {
            port: None,
            warming: false,
        });
    };
    let client = http_client();
    let url = format!("http://127.0.0.1:{port}/api/status");
    match client.get(&url).send().await {
        Ok(res) if res.status().is_success() => {
            let body: Value = res.json().await.unwrap_or(Value::Null);
            let warming = body
                .get("desk_warming")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            Ok(HermesDeskBootState {
                port: Some(port),
                warming,
            })
        }
        _ => Ok(HermesDeskBootState {
            port: Some(port),
            warming: true,
        }),
    }
}
