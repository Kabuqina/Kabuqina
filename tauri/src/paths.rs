// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Path helpers + workspace setup.

use anyhow::{Context, Result};
use serde::Serialize;
use std::path::{Component, Path, PathBuf};
use tauri::{AppHandle, Manager};

const SETTING_POWER_USER: &str = "hermesdesk.power_user";
const SETTING_WORKSPACE: &str = "hermesdesk.workspace";
const SETTING_SHOW_RECIPE_MARKET: &str = "hermesdesk.show_recipe_market";
const SETTING_AUTO_GATEWAY: &str = "hermesdesk.auto_start_gateway";

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
/// Set `HERMESDESK_RUNTIME_DIR` to an absolute path to force the bundle (e.g. after
/// `build_bundle.ps1` when automatic discovery fails).
fn runtime_has_python(dir: &Path) -> bool {
    dir.join("python").join("python.exe").is_file()
}

pub fn resolve_runtime_dir(app: &AppHandle) -> Result<PathBuf> {
    if let Ok(force) = std::env::var("HERMESDESK_RUNTIME_DIR") {
        let p = PathBuf::from(force.trim());
        if runtime_has_python(&p) {
            return Ok(p);
        }
        anyhow::bail!(
            "HERMESDESK_RUNTIME_DIR is set but python.exe not found under {}",
            p.display()
        );
    }

    let mut tried: Vec<PathBuf> = Vec::new();

    // Portable zip / MSI layout: runtime next to kabuqina.exe (see package-portable-windows.ps1).
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            for rel in ["resources/runtime", "runtime"] {
                let candidate = exe_dir.join(rel);
                tried.push(candidate.clone());
                if runtime_has_python(&candidate) {
                    return Ok(candidate);
                }
            }

            // Dev only: `repo/tauri/target/{debug,release}/kabuqina.exe` → prefer fresh
            // `python/dist/runtime` over a stale `target/.../runtime` copy.
            let exe_lossy = exe.to_string_lossy();
            if exe_lossy.contains("\\target\\release\\") || exe_lossy.contains("\\target\\debug\\")
            {
                if let Some(repo_root) = exe
                    .parent()
                    .and_then(|p| p.parent())
                    .and_then(|p| p.parent())
                    .and_then(|p| p.parent())
                {
                    let from_repo = repo_root.join("python").join("dist").join("runtime");
                    tried.push(from_repo.clone());
                    if runtime_has_python(&from_repo) {
                        return Ok(from_repo);
                    }
                }
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
    let path = dir.join("hermesdesk_show_recipe_market.txt");
    let bytes: &[u8] = if is_show_recipe_market(app) {
        b"1\n"
    } else {
        b"0\n"
    };
    std::fs::write(&path, bytes).with_context(|| format!("writing {}", path.display()))?;
    Ok(())
}

fn read_setting(app: &AppHandle, _key: &str) -> Option<String> {
    // Tiny KV store backed by a JSON file under app_local_data_dir; we keep
    // the implementation here intentionally simple.
    let data_dir = app.path().app_local_data_dir().ok()?;
    let f = data_dir.join("settings.json");
    let raw = std::fs::read_to_string(f).ok()?;
    let v: serde_json::Value = serde_json::from_str(&raw).ok()?;
    v.get(_key).and_then(|x| x.as_str()).map(|s| s.to_string())
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
fn resolve_workspace_child(app: &AppHandle, path: &str) -> Result<PathBuf, String> {
    let workspace = ensure_workspace(app).map_err(|e| e.to_string())?;
    let ws_canon = std::fs::canonicalize(&workspace).unwrap_or(workspace);
    let canon = std::fs::canonicalize(PathBuf::from(path))
        .map_err(|e| format!("path not found: {}", e))?;
    if !canon.starts_with(&ws_canon) {
        return Err("path is outside the workspace".into());
    }
    Ok(canon)
}

/// Open a workspace file with the OS default application.
#[tauri::command]
pub fn cmd_open_path(app: AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let target = resolve_workspace_child(&app, &path)?;
    app.opener()
        .open_path(target.to_string_lossy(), None::<&str>)
        .map_err(|e| e.to_string())
}

/// Reveal a workspace file in the system file manager (Explorer / Finder).
#[tauri::command]
pub fn cmd_reveal_path(app: AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let target = resolve_workspace_child(&app, &path)?;
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

/// Persist the flag; callers that need new `HERMESDESK_POWER_USER` in the child
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
    write_setting(&app, "hermesdesk.personality", &name).map_err(|e| e.to_string())
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

/// ``<data_dir>/hermes-home/shared/USER_PREFS.md``
fn shared_prefs_path(data_dir: &PathBuf) -> PathBuf {
    let home = data_dir.join("hermes-home");
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
        cmd_write_text_file, migrate_workspace_contents, parse_auto_start_gateway_setting,
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
}
