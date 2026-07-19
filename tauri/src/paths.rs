// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Path helpers + workspace setup.

use anyhow::{Context, Result};
use base64::Engine;
use serde::Serialize;
use serde_json::json;
use std::path::{Component, Path, PathBuf};
use tauri::{AppHandle, Manager};

const SETTING_POWER_USER: &str = "kabuqina.power_user";
const SETTING_WORKSPACE: &str = "kabuqina.workspace";
const SETTING_SHOW_RECIPE_MARKET: &str = "kabuqina.show_recipe_market";
const SETTING_AUTO_GATEWAY: &str = "kabuqina.auto_start_gateway";

#[derive(Debug, Clone, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceMigrationSummary {
    pub copied_files: u64,
    pub copied_dirs: u64,
    pub conflicts: u64,
    pub skipped_entries: u64,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceUpdateResult {
    pub workspace: String,
    pub migrated: bool,
    pub copied_files: u64,
    pub copied_dirs: u64,
    pub conflicts: u64,
    pub skipped_entries: u64,
}

/// Resolve `%USERPROFILE%\Documents\KabuqinaWork`, creating it if missing.
pub fn ensure_workspace(app: &AppHandle) -> Result<PathBuf> {
    let custom = read_setting(app, SETTING_WORKSPACE);
    let chosen = match custom {
        Some(p) if !p.is_empty() => PathBuf::from(p),
        _ => default_workspace(app)?,
    };
    std::fs::create_dir_all(&chosen)
        .with_context(|| format!("creating workspace {}", chosen.display()))?;
    Ok(chosen)
}

fn default_workspace(app: &AppHandle) -> Result<PathBuf> {
    let docs = app.path().document_dir().context("document dir")?;
    Ok(docs.join("KabuqinaWork"))
}

/// Writable per-user app state (resolved by Tauri from the app identifier).
pub fn ensure_data_dir(app: &AppHandle) -> Result<PathBuf> {
    let dir = app.path().app_local_data_dir().context("local data dir")?;
    std::fs::create_dir_all(&dir).with_context(|| format!("creating {}", dir.display()))?;
    Ok(dir)
}

/// Find the bundled Python runtime. In dev: `python/dist/runtime` at the repo root
/// (see `../python/dist/runtime` in `tauri.conf.json` for release bundles).
/// In prod: `resources/runtime` next to the installed app.
///
/// Set `KABUQINA_RUNTIME_DIR` to an absolute path to force the bundle (e.g. after
/// `build_bundle.ps1` when automatic discovery fails).
fn runtime_has_python(dir: &Path) -> bool {
    dir.join("python").join("python.exe").is_file()
}

fn dev_repo_runtime_candidate(exe: &Path) -> Option<PathBuf> {
    let exe_lossy = exe.to_string_lossy();
    if !(exe_lossy.contains("\\target\\release\\") || exe_lossy.contains("\\target\\debug\\")) {
        return None;
    }
    let repo_root = exe
        .parent()
        .and_then(|p| p.parent())
        .and_then(|p| p.parent())
        .and_then(|p| p.parent())?;
    Some(repo_root.join("python").join("dist").join("runtime"))
}

fn runtime_candidates_from_exe(exe: &Path) -> Vec<PathBuf> {
    let mut candidates = Vec::new();
    if let Some(from_repo) = dev_repo_runtime_candidate(exe) {
        candidates.push(from_repo);
    }
    if let Some(exe_dir) = exe.parent() {
        candidates.push(exe_dir.join("resources/runtime"));
        candidates.push(exe_dir.join("runtime"));
    }
    candidates
}

pub fn resolve_runtime_dir(app: &AppHandle) -> Result<PathBuf> {
    if let Ok(force) =
        std::env::var("KABUQINA_RUNTIME_DIR").or_else(|_| std::env::var("HERMESDESK_RUNTIME_DIR"))
    {
        let p = PathBuf::from(force.trim());
        if runtime_has_python(&p) {
            return Ok(p);
        }
        anyhow::bail!(
            "KABUQINA_RUNTIME_DIR is set but python.exe not found under {}",
            p.display()
        );
    }

    let mut tried: Vec<PathBuf> = Vec::new();

    // Dev target binaries prefer the freshly synced repo runtime. Packaged apps
    // still look beside kabuqina.exe (see package-portable-windows.ps1).
    if let Ok(exe) = std::env::current_exe() {
        for candidate in runtime_candidates_from_exe(&exe) {
            tried.push(candidate.clone());
            if runtime_has_python(&candidate) {
                return Ok(candidate);
            }
        }
    }

    let res = app.path().resource_dir().context("resource dir")?;
    let candidate = res.join("runtime");
    tried.push(candidate.clone());
    if runtime_has_python(&candidate) {
        return Ok(candidate);
    }

    let list = tried
        .iter()
        .map(|p| p.display().to_string())
        .collect::<Vec<_>>()
        .join("; ");
    anyhow::bail!("Could not locate bundled Python runtime. Tried: {list}")
}

pub fn is_power_user(app: &AppHandle) -> bool {
    // Off until explicitly enabled. Onboarding (Welcome step) and the Settings
    // toggle both persist this via `set_power_user_enabled`; we never silently
    // enable terminal/code-execution for users who skip that choice.
    matches!(
        read_setting(app, SETTING_POWER_USER).as_deref(),
        Some("1" | "true")
    )
}

pub fn is_show_recipe_market(app: &AppHandle) -> bool {
    matches!(
        read_setting(app, SETTING_SHOW_RECIPE_MARKET).as_deref(),
        Some("1" | "true")
    )
}

/// Gateway startup is manual-only. Older builds may have persisted this setting,
/// but current builds ignore it so app launch never polls messaging platforms.
pub fn is_auto_start_gateway(app: &AppHandle) -> bool {
    parse_auto_start_gateway_setting(read_setting(app, SETTING_AUTO_GATEWAY).as_deref())
}

fn parse_auto_start_gateway_setting(value: Option<&str>) -> bool {
    let _ = value;
    false
}

pub fn set_auto_start_gateway_enabled(app: &AppHandle, enabled: bool) -> Result<(), String> {
    write_setting(app, SETTING_AUTO_GATEWAY, if enabled { "1" } else { "0" })
        .map_err(|e| e.to_string())
}

/// Mirror the setting into the data dir so embedded Python can read `/api/status` without a process restart.
pub fn sync_show_recipe_market_flag(app: &AppHandle) -> Result<()> {
    let dir = ensure_data_dir(app)?;
    let path = dir.join("kabuqina_show_recipe_market.txt");
    let bytes: &[u8] = if is_show_recipe_market(app) {
        b"1\n"
    } else {
        b"0\n"
    };
    std::fs::write(&path, bytes).with_context(|| format!("writing {}", path.display()))?;
    Ok(())
}

fn legacy_setting_key(key: &str) -> Option<String> {
    key.strip_prefix("kabuqina.")
        .map(|suffix| format!("hermesdesk.{suffix}"))
}

fn read_setting(app: &AppHandle, key: &str) -> Option<String> {
    // Tiny KV store backed by a JSON file under app_local_data_dir; we keep
    // the implementation here intentionally simple.
    let data_dir = app.path().app_local_data_dir().ok()?;
    let f = data_dir.join("settings.json");
    let raw = std::fs::read_to_string(f).ok()?;
    let v: serde_json::Value = serde_json::from_str(&raw).ok()?;
    let value = v
        .get(key)
        .or_else(|| {
            legacy_setting_key(key)
                .as_ref()
                .and_then(|legacy| v.get(legacy))
        })
        .and_then(|x| x.as_str())
        .map(|s| s.to_string());
    if v.get(key).is_none() {
        if let Some(ref migrated) = value {
            let _ = write_setting(app, key, migrated);
        }
    }
    value
}

/// Default product profile when settings are missing or unknown.
pub const DEFAULT_PRODUCT_PROFILE: &str = "mainland_cn";

/// Resolve the active region product profile from `settings.json` (flat
/// `product_profile` key). Missing values resolve to `mainland_cn`; an
/// explicitly unknown value is preserved as `invalid` so gateway-producing
/// boundaries fail closed rather than inheriting another region.
pub fn resolve_product_profile(app: &AppHandle) -> String {
    let raw = read_setting(app, "product_profile").unwrap_or_default();
    let normalized = raw.trim().to_lowercase();
    match normalized.as_str() {
        "" => DEFAULT_PRODUCT_PROFILE.to_string(),
        "mainland_cn" => "mainland_cn".to_string(),
        "sea" => "sea".to_string(),
        _ => "invalid".to_string(),
    }
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ProductProfileContract {
    pub contract_version: &'static str,
    pub profile: String,
    pub visible_gateways: Vec<&'static str>,
}

#[tauri::command]
pub fn cmd_product_profile_contract(app: AppHandle) -> ProductProfileContract {
    let profile = resolve_product_profile(&app);
    let visible_gateways = match profile.as_str() {
        "mainland_cn" => vec!["weixin", "qqbot", "dingtalk"],
        "sea" => vec!["telegram", "whatsapp", "email"],
        _ => Vec::new(),
    };
    ProductProfileContract {
        contract_version: "kabuqina.platform-surface/v1",
        profile,
        visible_gateways,
    }
}

pub fn ensure_profile_platform_visible(app: &AppHandle, platform: &str) -> Result<(), String> {
    let profile = resolve_product_profile(app);
    if profile_allows_platform(&profile, platform) {
        Ok(())
    } else {
        Err(format!(
            "platform_unavailable [kabuqina.platform-surface/v1]: {platform:?} is not available in product profile {profile:?}"
        ))
    }
}

pub fn profile_allows_platform(profile: &str, platform: &str) -> bool {
    match profile {
        "mainland_cn" => matches!(platform, "weixin" | "qqbot" | "dingtalk"),
        "sea" => matches!(platform, "telegram" | "whatsapp" | "email"),
        _ => false,
    }
}

pub fn gateway_platform_for_env_key(key: &str) -> Option<&'static str> {
    let key = key.trim().to_ascii_uppercase();
    if key.starts_with("WEIXIN_") {
        Some("weixin")
    } else if key.starts_with("QQ_") || key.starts_with("QQBOT_") {
        Some("qqbot")
    } else if key.starts_with("DINGTALK_") {
        Some("dingtalk")
    } else if key.starts_with("TELEGRAM_") {
        Some("telegram")
    } else if key.starts_with("WHATSAPP_") {
        Some("whatsapp")
    } else if key.starts_with("EMAIL_") {
        Some("email")
    } else {
        None
    }
}

pub fn ensure_profile_env_key_writable(app: &AppHandle, key: &str) -> Result<(), String> {
    let platform = gateway_platform_for_env_key(key).ok_or_else(|| {
        format!(
            "platform_unavailable [kabuqina.platform-surface/v1]: env key {:?} is not writable by the gateway settings boundary",
            key.trim()
        )
    })?;
    ensure_profile_platform_visible(app, platform)
}

// ---- IPC commands ---------------------------------------------------------

#[tauri::command]
pub fn cmd_workspace_path(app: AppHandle) -> Result<String, String> {
    ensure_workspace(&app)
        .map(|p| p.display().to_string())
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn cmd_open_workspace(app: AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let p = ensure_workspace(&app).map_err(|e| e.to_string())?;
    app.opener()
        .open_path(p.to_string_lossy(), None::<&str>)
        .map_err(|e| e.to_string())
}

/// Resolve `path` and confirm it lives inside the workspace before handing it to
/// the OS opener. Deliverable paths shown in the workspace panel are extracted
/// from agent messages via regex, so we never open an arbitrary location a
/// crafted message could point at.
/// Resolve a path the UI asked to open or reveal, allowing only files that live
/// inside a directory Kabuqina manages. The path must exist on disk and sit
/// under one of:
///   * the user workspace (where document writers — pptx/docx/pdf/html — save), or
///   * the app's Hermes home (`<data_dir>/kabuqina-home`), where generated
///     artifacts that are not deliverables-proper land — notably browser
///     screenshots at `cache/screenshots/*.png`.
///
/// Anything else (e.g. an arbitrary `C:\Windows\...` path injected via chat) or
/// a non-existent path is rejected.
fn resolve_openable_path(app: &AppHandle, path: &str) -> Result<PathBuf, String> {
    let canon =
        std::fs::canonicalize(PathBuf::from(path)).map_err(|e| format!("path not found: {}", e))?;

    // Collect the allowed roots, canonicalized so the prefix check below compares
    // like-for-like with `canon` (matters on Windows, where canonicalize returns
    // the `\\?\` verbatim form).
    let mut roots: Vec<PathBuf> = Vec::new();
    if let Ok(workspace) = ensure_workspace(app) {
        roots.push(std::fs::canonicalize(&workspace).unwrap_or(workspace));
    }
    if let Ok(data_dir) = ensure_data_dir(app) {
        let home = crate::gateway_supervisor::kabuqina_home_path(&data_dir);
        if let Ok(home_canon) = std::fs::canonicalize(&home) {
            roots.push(home_canon);
        }
    }

    if roots.iter().any(|root| canon.starts_with(root)) {
        Ok(canon)
    } else {
        Err("path is outside the workspace".into())
    }
}

/// Open a workspace file with the OS default application.
#[tauri::command]
pub fn cmd_open_path(app: AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let target = resolve_openable_path(&app, &path)?;
    app.opener()
        .open_path(target.to_string_lossy(), None::<&str>)
        .map_err(|e| e.to_string())
}

/// Reveal a workspace file in the system file manager (Explorer / Finder).
#[tauri::command]
pub fn cmd_reveal_path(app: AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let target = resolve_openable_path(&app, &path)?;
    app.opener()
        .reveal_item_in_dir(&target)
        .map_err(|e| e.to_string())
}

pub fn set_workspace_path(
    app: &AppHandle,
    path_str: String,
    migrate_files: bool,
) -> Result<WorkspaceUpdateResult, String> {
    let previous = ensure_workspace(app).map_err(|e| e.to_string())?;
    let trimmed = path_str.trim();
    let target = if trimmed.is_empty() {
        default_workspace(app).map_err(|e| e.to_string())?
    } else {
        PathBuf::from(trimmed)
    };
    if !target.is_absolute() {
        return Err("Workspace path must be absolute.".into());
    }

    let normalized_target = normalize_path_lexically(&target);
    let normalized_previous = normalize_path_lexically(&previous);
    let same_path = normalized_paths_equal(&normalized_previous, &normalized_target);
    let mut summary = WorkspaceMigrationSummary::default();
    if migrate_files && !same_path {
        summary = migrate_workspace_contents(&normalized_previous, &normalized_target)
            .map_err(|e| e.to_string())?;
    } else {
        std::fs::create_dir_all(&normalized_target)
            .map_err(|e| format!("creating workspace {}: {e}", normalized_target.display()))?;
    }

    write_setting(app, SETTING_WORKSPACE, trimmed).map_err(|e| e.to_string())?;
    Ok(WorkspaceUpdateResult {
        workspace: normalized_target.display().to_string(),
        migrated: migrate_files && !same_path,
        copied_files: summary.copied_files,
        copied_dirs: summary.copied_dirs,
        conflicts: summary.conflicts,
        skipped_entries: summary.skipped_entries,
    })
}

pub fn migrate_workspace_contents(
    source: &Path,
    destination: &Path,
) -> Result<WorkspaceMigrationSummary> {
    let source = normalize_path_lexically(source);
    let destination = normalize_path_lexically(destination);
    if normalized_path_is_within(&destination, &source) {
        anyhow::bail!("new workspace cannot be inside the current workspace");
    }
    if !source.exists() {
        std::fs::create_dir_all(&destination)
            .with_context(|| format!("creating workspace {}", destination.display()))?;
        return Ok(WorkspaceMigrationSummary::default());
    }

    std::fs::create_dir_all(&destination)
        .with_context(|| format!("creating workspace {}", destination.display()))?;
    let mut summary = WorkspaceMigrationSummary::default();
    copy_workspace_dir(&source, &destination, &mut summary)?;
    Ok(summary)
}

fn copy_workspace_dir(
    source: &Path,
    destination: &Path,
    summary: &mut WorkspaceMigrationSummary,
) -> Result<()> {
    for entry in std::fs::read_dir(source)
        .with_context(|| format!("reading workspace {}", source.display()))?
    {
        let entry = entry?;
        if is_reserved_windows_device_name(&entry.file_name().to_string_lossy()) {
            summary.skipped_entries += 1;
            continue;
        }
        let from = entry.path();
        let rel = from.strip_prefix(source).unwrap_or(&from);
        let to = destination.join(rel);
        let meta = std::fs::symlink_metadata(&from)
            .with_context(|| format!("reading metadata {}", from.display()))?;
        let file_type = meta.file_type();
        if file_type.is_symlink() {
            summary.skipped_entries += 1;
            continue;
        }
        if meta.is_dir() {
            if !to.exists() {
                std::fs::create_dir_all(&to)
                    .with_context(|| format!("creating directory {}", to.display()))?;
                summary.copied_dirs += 1;
            }
            copy_workspace_dir(&from, &to, summary)?;
        } else if meta.is_file() {
            if to.exists() {
                summary.conflicts += 1;
                continue;
            }
            if let Some(parent) = to.parent() {
                std::fs::create_dir_all(parent)
                    .with_context(|| format!("creating directory {}", parent.display()))?;
            }
            std::fs::copy(&from, &to)
                .with_context(|| format!("copying {} to {}", from.display(), to.display()))?;
            summary.copied_files += 1;
        } else {
            summary.skipped_entries += 1;
        }
    }
    Ok(())
}

fn is_reserved_windows_device_name(name: &str) -> bool {
    let trimmed = name.trim_end_matches([' ', '.']);
    let stem = trimmed
        .split(['.', ':'])
        .next()
        .unwrap_or(trimmed)
        .to_ascii_lowercase();
    matches!(stem.as_str(), "con" | "prn" | "aux" | "nul")
        || (stem.len() == 4
            && (stem.starts_with("com") || stem.starts_with("lpt"))
            && matches!(stem.as_bytes()[3], b'1'..=b'9'))
}

fn write_setting(app: &AppHandle, key: &str, value: &str) -> Result<()> {
    let dir = app.path().app_local_data_dir().context("local data dir")?;
    std::fs::create_dir_all(&dir)?;
    let f = dir.join("settings.json");
    let mut v: serde_json::Value = std::fs::read_to_string(&f)
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or(serde_json::json!({}));
    v[key] = serde_json::Value::String(value.to_string());
    std::fs::write(&f, serde_json::to_vec_pretty(&v)?)?;
    Ok(())
}

#[tauri::command]
pub fn cmd_get_power_user(app: AppHandle) -> Result<bool, String> {
    Ok(is_power_user(&app))
}

/// Persist the flag; callers that need new `KABUQINA_POWER_USER` in the child
/// must restart embedded Python (see `lib::respawn_embedded_hermes_python`).
pub fn set_power_user_enabled(app: &AppHandle, enabled: bool) -> Result<(), String> {
    write_setting(app, SETTING_POWER_USER, if enabled { "1" } else { "0" })
        .map_err(|e| e.to_string())
}

#[tauri::command]
pub fn cmd_get_show_recipe_market(app: AppHandle) -> Result<bool, String> {
    Ok(is_show_recipe_market(&app))
}

#[tauri::command]
pub fn cmd_set_show_recipe_market(app: AppHandle, enabled: bool) -> Result<(), String> {
    write_setting(
        &app,
        SETTING_SHOW_RECIPE_MARKET,
        if enabled { "1" } else { "0" },
    )
    .map_err(|e| e.to_string())?;
    sync_show_recipe_market_flag(&app).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn cmd_set_personality(app: AppHandle, name: String) -> Result<(), String> {
    write_setting(&app, "kabuqina.personality", &name).map_err(|e| e.to_string())
}

#[tauri::command]
pub fn cmd_get_auto_start_gateway(app: AppHandle) -> Result<bool, String> {
    Ok(is_auto_start_gateway(&app))
}

#[tauri::command]
pub fn cmd_set_auto_start_gateway(app: AppHandle, enabled: bool) -> Result<(), String> {
    set_auto_start_gateway_enabled(&app, enabled)
}

// ---- Shared user preferences (host-only write, bot-read-only) ----------------

/// ``<data_dir>/kabuqina-home/shared/USER_PREFS.md``
fn shared_prefs_path(data_dir: &PathBuf) -> PathBuf {
    let home = crate::gateway_supervisor::kabuqina_home_path(data_dir);
    home.join("shared").join("USER_PREFS.md")
}

/// Read the shared preferences file (used by all bots as read-only preamble).
/// Returns an empty string if the file does not exist or is empty.
#[tauri::command]
pub fn cmd_read_shared_prefs(app: AppHandle) -> Result<String, String> {
    let data_dir = ensure_data_dir(&app).map_err(|e| e.to_string())?;
    let path = shared_prefs_path(&data_dir);
    match std::fs::read_to_string(&path) {
        Ok(content) => Ok(content),
        Err(_) => Ok(String::new()),
    }
}

/// Write a text file to a path chosen by the user via the save dialog.
///
/// Rejects paths that target sensitive system locations (Windows, Program
/// Files, startup folders) to prevent abuse if the IPC is ever reached
/// without a genuine save-dialog interaction.
#[tauri::command]
pub fn cmd_write_text_file(path_str: String, content: String) -> Result<(), String> {
    use std::io::Write;
    let path = std::path::PathBuf::from(&path_str);
    let path = validate_text_export_path(&path)?;

    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("create dir: {e}"))?;
    }
    let mut f = std::fs::File::create(&path).map_err(|e| format!("open {path_str:?}: {e}"))?;
    f.write_all(content.as_bytes())
        .map_err(|e| format!("write {path_str:?}: {e}"))?;
    Ok(())
}

/// Write a real PDF generated from an internal HTML print source.
///
/// The caller supplies HTML content, not a URL or source file path. This keeps
/// filesystem reads host-owned and limits output to the same user export roots
/// as text exports.
#[tauri::command]
pub async fn cmd_write_pdf_from_html(
    app: AppHandle,
    path_str: String,
    html: String,
) -> Result<(), String> {
    let path = std::path::PathBuf::from(&path_str);
    let path = validate_pdf_export_path(&path)?;
    if html.trim().is_empty() {
        return Err("PDF export HTML cannot be empty".into());
    }
    let payload = crate::chat::desk_json_request(
        &app,
        reqwest::Method::POST,
        "/api/desk/export/pdf",
        Some(json!({ "html": html })),
    )
    .await?;
    let pdf_b64 = payload
        .get("pdfBase64")
        .and_then(|v| v.as_str())
        .ok_or_else(|| "PDF renderer returned no pdfBase64 payload".to_string())?;
    let pdf_bytes = base64::engine::general_purpose::STANDARD
        .decode(pdf_b64)
        .map_err(|e| format!("decode PDF payload: {e}"))?;
    if !pdf_bytes.starts_with(b"%PDF-") {
        return Err("PDF renderer did not produce a valid PDF file".into());
    }

    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("create PDF export dir: {e}"))?;
    }
    std::fs::write(&path, pdf_bytes).map_err(|e| format!("write PDF export: {e}"))?;
    Ok(())
}

fn validate_text_export_path(path: &Path) -> Result<PathBuf, String> {
    if !path.is_absolute() {
        return Err("Export path must be absolute".into());
    }

    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_ascii_lowercase())
        .ok_or_else(|| "Export path must have a text file extension".to_string())?;
    if !matches!(ext.as_str(), "json" | "md" | "markdown" | "txt") {
        return Err("Export path must end in .json, .md, .markdown, or .txt".into());
    }

    let normalized = normalize_path_lexically(path);
    let allowed = known_export_roots();
    if !allowed.iter().any(|root| path_is_within(&normalized, root)) {
        return Err("Exports can only be saved under Desktop, Documents, or Downloads".into());
    }

    Ok(normalized)
}

fn validate_pdf_export_path(path: &Path) -> Result<PathBuf, String> {
    if !path.is_absolute() {
        return Err("PDF export path must be absolute".into());
    }

    let ext = path
        .extension()
        .and_then(|s| s.to_str())
        .map(|s| s.to_ascii_lowercase())
        .ok_or_else(|| "PDF export path must end in .pdf".to_string())?;
    if ext != "pdf" {
        return Err("PDF export path must end in .pdf".into());
    }

    let normalized = normalize_path_lexically(path);
    let allowed = known_export_roots();
    if !allowed.iter().any(|root| path_is_within(&normalized, root)) {
        return Err("PDF exports can only be saved under Desktop, Documents, or Downloads".into());
    }

    Ok(normalized)
}

fn known_export_roots() -> Vec<PathBuf> {
    let Some(profile) = std::env::var_os("USERPROFILE").map(PathBuf::from) else {
        return Vec::new();
    };
    ["Desktop", "Documents", "Downloads"]
        .iter()
        .map(|name| normalize_path_lexically(&profile.join(name)))
        .collect()
}

fn path_is_within(path: &Path, root: &Path) -> bool {
    path == root || path.starts_with(root)
}

fn normalized_paths_equal(left: &Path, right: &Path) -> bool {
    normalized_components_lower(left) == normalized_components_lower(right)
}

fn normalized_path_is_within(path: &Path, root: &Path) -> bool {
    let path_components = normalized_components_lower(path);
    let root_components = normalized_components_lower(root);
    path_components == root_components || path_components.starts_with(&root_components)
}

fn normalized_components_lower(path: &Path) -> Vec<String> {
    normalize_path_lexically(path)
        .components()
        .map(|component| component.as_os_str().to_string_lossy().to_ascii_lowercase())
        .collect()
}

fn normalize_path_lexically(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                out.pop();
            }
            other => out.push(other.as_os_str()),
        }
    }
    out
}

/// Write (overwrite) the shared preferences file.
/// This is a host-only operation (desktop agent). Bots never call this.
#[tauri::command]
pub fn cmd_save_shared_prefs(app: AppHandle, content: String) -> Result<(), String> {
    use std::io::Write;
    let data_dir = ensure_data_dir(&app).map_err(|e| e.to_string())?;
    let path = shared_prefs_path(&data_dir);
    // Ensure parent dir exists.
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("create shared dir: {e}"))?;
    }
    let mut f = std::fs::File::create(&path).map_err(|e| format!("open {path:?}: {e}"))?;
    f.write_all(content.as_bytes())
        .map_err(|e| format!("write {path:?}: {e}"))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{
        cmd_write_text_file, gateway_platform_for_env_key, is_reserved_windows_device_name,
        migrate_workspace_contents, parse_auto_start_gateway_setting, profile_allows_platform,
        runtime_candidates_from_exe, validate_pdf_export_path, validate_text_export_path,
    };

    fn unique_temp_path(name: &str) -> std::path::PathBuf {
        std::env::temp_dir().join(format!("kabuqina-path-test-{}-{name}", std::process::id()))
    }

    #[test]
    fn write_text_file_rejects_untrusted_temp_path() {
        let path = unique_temp_path("export.md");
        let _ = std::fs::remove_file(&path);

        let result = cmd_write_text_file(path.display().to_string(), "hello".to_string());

        assert!(result.is_err());
        assert!(!path.exists());
    }

    #[test]
    fn write_text_file_rejects_script_extension() {
        let path = unique_temp_path("profile.ps1");
        let _ = std::fs::remove_file(&path);

        let result = cmd_write_text_file(path.display().to_string(), "Write-Host hi".to_string());

        assert!(result.is_err());
        assert!(!path.exists());
    }

    #[test]
    fn pdf_export_path_validation() {
        let profile = std::env::var_os("USERPROFILE").expect("USERPROFILE should exist on Windows");
        let desktop = std::path::PathBuf::from(profile).join("Desktop");

        assert!(validate_text_export_path(&desktop.join("chat.pdf")).is_err());
        assert!(validate_pdf_export_path(&desktop.join("chat.pdf")).is_ok());
        assert!(validate_pdf_export_path(&desktop.join("chat.txt")).is_err());
        assert!(validate_pdf_export_path(&unique_temp_path("chat.pdf")).is_err());
    }

    #[test]
    fn auto_start_gateway_defaults_to_manual_start() {
        assert!(!parse_auto_start_gateway_setting(None));
    }

    #[test]
    fn auto_start_gateway_ignores_legacy_enabled_setting() {
        assert!(!parse_auto_start_gateway_setting(Some("1")));
        assert!(!parse_auto_start_gateway_setting(Some("true")));
        assert!(!parse_auto_start_gateway_setting(Some("yes")));
    }

    #[test]
    fn dev_runtime_candidates_prefer_repo_dist_runtime() {
        let exe = std::path::PathBuf::from(r"C:\repo\Kabuqina\tauri\target\debug\kabuqina.exe");

        let candidates = runtime_candidates_from_exe(&exe);

        assert_eq!(
            candidates[0],
            std::path::PathBuf::from(r"C:\repo\Kabuqina\python\dist\runtime")
        );
        assert_eq!(
            candidates[1],
            std::path::PathBuf::from(r"C:\repo\Kabuqina\tauri\target\debug\resources\runtime")
        );
        assert_eq!(
            candidates[2],
            std::path::PathBuf::from(r"C:\repo\Kabuqina\tauri\target\debug\runtime")
        );
    }

    #[test]
    fn detects_reserved_windows_device_names_before_metadata_reads() {
        for name in [
            "nul", "NUL", "nul.txt", "con", "prn.md", "aux", "com1", "COM9.log", "lpt1",
        ] {
            assert!(is_reserved_windows_device_name(name), "{name}");
        }
        for name in ["notes.md", "null.md", "company1.txt", "lpt10.txt"] {
            assert!(!is_reserved_windows_device_name(name), "{name}");
        }
    }

    #[test]
    fn migrate_workspace_copies_nested_and_hidden_files() {
        let root = unique_temp_path("workspace-copy");
        let old = root.join("old");
        let new = root.join("new");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(old.join(".hermesdesk")).unwrap();
        std::fs::create_dir_all(old.join("notes")).unwrap();
        std::fs::write(old.join(".hermesdesk").join("state.json"), "{}").unwrap();
        std::fs::write(old.join("notes").join("draft.md"), "hello").unwrap();

        let summary = migrate_workspace_contents(&old, &new).unwrap();

        assert_eq!(summary.copied_files, 2);
        assert_eq!(summary.conflicts, 0);
        assert_eq!(
            std::fs::read_to_string(new.join(".hermesdesk").join("state.json")).unwrap(),
            "{}"
        );
        assert_eq!(
            std::fs::read_to_string(new.join("notes").join("draft.md")).unwrap(),
            "hello"
        );

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn migrate_workspace_keeps_existing_destination_files() {
        let root = unique_temp_path("workspace-conflict");
        let old = root.join("old");
        let new = root.join("new");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&old).unwrap();
        std::fs::create_dir_all(&new).unwrap();
        std::fs::write(old.join("draft.md"), "old").unwrap();
        std::fs::write(new.join("draft.md"), "new").unwrap();

        let summary = migrate_workspace_contents(&old, &new).unwrap();

        assert_eq!(summary.copied_files, 0);
        assert_eq!(summary.conflicts, 1);
        assert_eq!(
            std::fs::read_to_string(new.join("draft.md")).unwrap(),
            "new"
        );

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn migrate_workspace_rejects_destination_inside_source() {
        let root = unique_temp_path("workspace-nested");
        let old = root.join("old");
        let new = old.join("child");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&old).unwrap();

        let result = migrate_workspace_contents(&old, &new);

        assert!(result.is_err());
        assert!(!new.exists());

        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn gateway_profile_platform_matrix_is_exact_and_unknown_is_closed() {
        assert!(profile_allows_platform("mainland_cn", "weixin"));
        assert!(profile_allows_platform("mainland_cn", "qqbot"));
        assert!(profile_allows_platform("mainland_cn", "dingtalk"));
        assert!(!profile_allows_platform("mainland_cn", "telegram"));
        assert!(profile_allows_platform("sea", "telegram"));
        assert!(profile_allows_platform("sea", "whatsapp"));
        assert!(profile_allows_platform("sea", "email"));
        assert!(!profile_allows_platform("sea", "weixin"));
        assert!(!profile_allows_platform("invalid", "email"));
    }

    #[test]
    fn gateway_env_key_mapping_rejects_removed_and_generic_namespaces() {
        assert_eq!(
            gateway_platform_for_env_key("WEIXIN_HOME_CHANNEL"),
            Some("weixin")
        );
        assert_eq!(
            gateway_platform_for_env_key("QQBOT_HOME_CHANNEL"),
            Some("qqbot")
        );
        assert_eq!(
            gateway_platform_for_env_key("EMAIL_ALLOWED_USERS"),
            Some("email")
        );
        for removed in [
            "FEISHU_APP_ID",
            "WECOM_SECRET",
            "DISCORD_BOT_TOKEN",
            "SMS_HOME_CHANNEL",
            "GATEWAY_ALLOW_ALL_USERS",
            "MALICIOUS_API_URL",
        ] {
            assert_eq!(gateway_platform_for_env_key(removed), None, "{removed}");
        }
    }
}
