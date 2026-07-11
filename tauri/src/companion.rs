// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Compact pill companion window (always-on-top mascot).

use serde::Deserialize;
use tauri::{
    AppHandle, LogicalSize, Manager, PhysicalPosition, Position, Size, WebviewWindow,
    WebviewWindowBuilder, WindowEvent,
};

const COMPANION_LABEL: &str = "companion";
/// Fallback when intrinsic size missing or invalid.
const COMPACT_FALLBACK_WIDTH: f64 = 87.0;
const COMPACT_FALLBACK_HEIGHT: f64 = 76.0;
const COMPACT_MIN_EDGE_LOGICAL: f64 = 48.0;
const COMPACT_MAX_EDGE_LOGICAL: f64 = 512.0;
const WINDOW_MIN_EDGE: f64 = 32.0;
const COMPANION_MARGIN_LOGICAL: f64 = 20.0;
const SETTING_COMPANION_X: &str = "kabuqina.companion_x";
const SETTING_COMPANION_Y: &str = "kabuqina.companion_y";
const SETTING_COMPANION_USER_PLACED: &str = "kabuqina.companion_user_placed";
/// Ignore spurious Moved(0,0) and legacy bad saves near the desktop origin.
const COMPANION_ORIGIN_GUARD_LOGICAL: f64 = 48.0;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResizeCompanionPayload {
    #[serde(default)]
    pub width: Option<f64>,
    #[serde(default)]
    pub height: Option<f64>,
}

fn clamp_compact_logical_size(width: f64, height: f64) -> (f64, f64) {
    if width <= 0.0 || height <= 0.0 || !width.is_finite() || !height.is_finite() {
        return (COMPACT_FALLBACK_WIDTH, COMPACT_FALLBACK_HEIGHT);
    }

    let mut w = width;
    let mut h = height;

    let max_edge = w.max(h);
    if max_edge > COMPACT_MAX_EDGE_LOGICAL {
        let s = COMPACT_MAX_EDGE_LOGICAL / max_edge;
        w *= s;
        h *= s;
    }

    let min_edge = w.min(h);
    if min_edge < COMPACT_MIN_EDGE_LOGICAL && min_edge > f64::EPSILON {
        let s = COMPACT_MIN_EDGE_LOGICAL / min_edge;
        w *= s;
        h *= s;
        let max_after = w.max(h);
        if max_after > COMPACT_MAX_EDGE_LOGICAL {
            let s2 = COMPACT_MAX_EDGE_LOGICAL / max_after;
            w *= s2;
            h *= s2;
        }
    }

    ((w.round()).max(1.0), (h.round()).max(1.0))
}

fn read_setting(app: &AppHandle, key: &str) -> Option<String> {
    let data_dir = app.path().app_local_data_dir().ok()?;
    let raw = std::fs::read_to_string(data_dir.join("settings.json")).ok()?;
    let v: serde_json::Value = serde_json::from_str(&raw).ok()?;
    let legacy_key = key
        .strip_prefix("kabuqina.")
        .map(|suffix| format!("hermesdesk.{suffix}"));
    let value = v.get(key)
        .or_else(|| legacy_key.as_ref().and_then(|legacy| v.get(legacy)))
        .and_then(|x| x.as_str())
        .map(|s| s.to_string());
    if v.get(key).is_none() {
        if let Some(ref migrated) = value {
            let _ = write_setting(app, key, migrated);
        }
    }
    value
}

fn write_setting(app: &AppHandle, key: &str, value: &str) -> Result<(), String> {
    let dir = app.path().app_local_data_dir().map_err(|e| e.to_string())?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let f = dir.join("settings.json");
    let mut v: serde_json::Value = std::fs::read_to_string(&f)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    v[key] = serde_json::Value::String(value.to_string());
    std::fs::write(
        &f,
        serde_json::to_vec_pretty(&v).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())
}

fn read_companion_saved_position(app: &AppHandle) -> Option<(f64, f64)> {
    let x: f64 = read_setting(app, SETTING_COMPANION_X)?.parse().ok()?;
    let y: f64 = read_setting(app, SETTING_COMPANION_Y)?.parse().ok()?;
    if !x.is_finite() || !y.is_finite() {
        return None;
    }
    let user_placed = read_setting(app, SETTING_COMPANION_USER_PLACED).as_deref() == Some("1");
    let away_from_origin =
        x >= COMPANION_ORIGIN_GUARD_LOGICAL || y >= COMPANION_ORIGIN_GUARD_LOGICAL;
    if user_placed || away_from_origin {
        Some((x, y))
    } else {
        None
    }
}

fn persist_companion_position(app: &AppHandle, x: f64, y: f64) {
    if x < COMPANION_ORIGIN_GUARD_LOGICAL && y < COMPANION_ORIGIN_GUARD_LOGICAL {
        return;
    }
    let _ = write_setting(app, SETTING_COMPANION_USER_PLACED, "1");
    let _ = write_setting(app, SETTING_COMPANION_X, &format!("{x:.2}"));
    let _ = write_setting(app, SETTING_COMPANION_Y, &format!("{y:.2}"));
}

fn reference_monitor(app: &AppHandle) -> Option<tauri::Monitor> {
    if let Some(w) = app.get_webview_window(COMPANION_LABEL) {
        if let Ok(Some(m)) = w.current_monitor() {
            return Some(m);
        }
    }
    if let Some(w) = app.get_webview_window("main") {
        if let Ok(Some(m)) = w.current_monitor() {
            return Some(m);
        }
    }
    app.primary_monitor().ok().flatten()
}

fn work_area_logical(monitor: &tauri::Monitor) -> (f64, f64, f64, f64) {
    let scale = monitor.scale_factor();
    let work = monitor.work_area();
    let left = work.position.x as f64 / scale;
    let top = work.position.y as f64 / scale;
    let right = (work.position.x as f64 + work.size.width as f64) / scale;
    let bottom = (work.position.y as f64 + work.size.height as f64) / scale;
    (left, top, right, bottom)
}

fn default_companion_logical_position(
    app: &AppHandle,
    win_w: f64,
    win_h: f64,
) -> Option<(f64, f64)> {
    let monitor = reference_monitor(app)?;
    let (left, top, right, bottom) = work_area_logical(&monitor);
    let margin = COMPANION_MARGIN_LOGICAL;
    let x = (right - win_w - margin).max(left + margin);
    let y = (bottom - win_h - margin).max(top + margin);
    Some((x.round(), y.round()))
}

fn clamp_companion_logical_position(
    app: &AppHandle,
    x: f64,
    y: f64,
    win_w: f64,
    win_h: f64,
) -> (f64, f64) {
    let Some(monitor) = reference_monitor(app) else {
        return (x.max(0.0), y.max(0.0));
    };
    let (left, top, right, bottom) = work_area_logical(&monitor);
    let margin = COMPANION_MARGIN_LOGICAL;
    let max_x = (right - win_w - margin).max(left + margin);
    let max_y = (bottom - win_h - margin).max(top + margin);
    let min_x = left + margin;
    let min_y = top + margin;
    (x.clamp(min_x, max_x).round(), y.clamp(min_y, max_y).round())
}

fn companion_logical_size(w: &WebviewWindow) -> (f64, f64) {
    match w.inner_size() {
        Ok(size) => {
            let scale = w.scale_factor().unwrap_or(1.0);
            (
                (size.width as f64 / scale).round().max(1.0),
                (size.height as f64 / scale).round().max(1.0),
            )
        }
        Err(_) => (COMPACT_FALLBACK_WIDTH, COMPACT_FALLBACK_HEIGHT),
    }
}

fn set_companion_logical_position(w: &WebviewWindow, x: f64, y: f64) -> Result<(), String> {
    let scale = w.scale_factor().unwrap_or(1.0);
    w.set_position(Position::Physical(PhysicalPosition {
        x: (x * scale).round() as i32,
        y: (y * scale).round() as i32,
    }))
    .map_err(|e| e.to_string())
}

pub fn ensure_companion_position(app: &AppHandle) -> Result<(), String> {
    let Some(w) = app.get_webview_window(COMPANION_LABEL) else {
        return Ok(());
    };

    let (win_w, win_h) = companion_logical_size(&w);
    let (x, y) = if let Some((saved_x, saved_y)) = read_companion_saved_position(app) {
        clamp_companion_logical_position(app, saved_x, saved_y, win_w, win_h)
    } else {
        default_companion_logical_position(app, win_w, win_h)
            .unwrap_or((COMPANION_MARGIN_LOGICAL, COMPANION_MARGIN_LOGICAL))
    };

    set_companion_logical_position(&w, x, y)
}

fn attach_companion_move_listener(app: &AppHandle, companion: &WebviewWindow) {
    let companion_for_event = companion.clone();
    let app_for_event = app.clone();
    companion.on_window_event(move |event| {
        if let WindowEvent::Moved(PhysicalPosition { x, y }) = event {
            let scale = companion_for_event.scale_factor().unwrap_or(1.0);
            persist_companion_position(&app_for_event, *x as f64 / scale, *y as f64 / scale);
        }
    });
}

fn set_companion_compact_size(
    app: &AppHandle,
    width: Option<f64>,
    height: Option<f64>,
) -> Result<(), String> {
    let Some(w) = app.get_webview_window(COMPANION_LABEL) else {
        return Ok(());
    };
    let (lw, lh) = match (width, height) {
        (Some(cw), Some(ch)) => clamp_compact_logical_size(cw, ch),
        _ => (COMPACT_FALLBACK_WIDTH, COMPACT_FALLBACK_HEIGHT),
    };
    w.set_size(Size::Logical(LogicalSize {
        width: lw,
        height: lh,
    }))
    .map_err(|e| e.to_string())?;
    ensure_companion_position(app)
}

pub async fn show_companion(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window(COMPANION_LABEL) {
        set_companion_compact_size(&app, None, None)?;
        let _ = w.set_shadow(false);
        ensure_companion_position(&app)?;
        let _ = w.show();
        let _ = w.set_focus();
        if let Some(main) = app.get_webview_window("main") {
            let _ = main.hide();
        }
        return Ok(());
    }

    let companion = WebviewWindowBuilder::new(
        &app,
        COMPANION_LABEL,
        tauri::WebviewUrl::App("index.html".into()),
    )
    .title("Kabuqina")
    .decorations(false)
    .always_on_top(true)
    .transparent(true)
    .shadow(false)
    .visible(false)
    .resizable(false)
    .inner_size(COMPACT_FALLBACK_WIDTH, COMPACT_FALLBACK_HEIGHT)
    .min_inner_size(WINDOW_MIN_EDGE, WINDOW_MIN_EDGE)
    .skip_taskbar(true)
    .build()
    .map_err(|e| format!("create companion window: {e}"))?;

    attach_companion_move_listener(&app, &companion);
    ensure_companion_position(&app)?;
    let _ = companion.show();
    let _ = companion.set_focus();
    if let Some(main) = app.get_webview_window("main") {
        let _ = main.hide();
    }

    Ok(())
}

pub fn focus_main_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
    if let Some(w) = app.get_webview_window(COMPANION_LABEL) {
        let _ = w.hide();
    }
}

#[tauri::command]
pub async fn cmd_show_companion(app: tauri::AppHandle) -> Result<(), String> {
    show_companion(app).await
}

#[tauri::command]
pub async fn cmd_hide_companion(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(w) = app.get_webview_window(COMPANION_LABEL) {
        let _ = w.hide();
    }
    Ok(())
}

#[tauri::command]
pub async fn cmd_resize_companion(
    app: tauri::AppHandle,
    payload: ResizeCompanionPayload,
) -> Result<(), String> {
    set_companion_compact_size(&app, payload.width, payload.height)
}

#[tauri::command]
pub async fn cmd_ensure_companion_position(app: tauri::AppHandle) -> Result<(), String> {
    ensure_companion_position(&app)
}

#[tauri::command]
pub async fn cmd_focus_main_window(app: tauri::AppHandle) -> Result<(), String> {
    focus_main_window(&app);
    Ok(())
}

#[cfg(test)]
mod tests {
    #[test]
    fn default_position_sits_in_work_area_bottom_right() {
        let left = 0.0_f64;
        let top = 0.0_f64;
        let right = 1920.0_f64;
        let bottom = 1040.0_f64;
        let win_w = 86.0_f64;
        let win_h = 75.0_f64;
        let margin = 20.0_f64;
        let x = (right - win_w - margin).max(left + margin);
        let y = (bottom - win_h - margin).max(top + margin);
        assert!(x > left + 100.0);
        assert!(y > top + 100.0);
        assert!(x + win_w <= right);
        assert!(y + win_h <= bottom);
    }
}
