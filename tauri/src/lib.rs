// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Kabuqina Tauri shell.
//!
//! Responsibilities:
//!  - Spawn and supervise the embedded Python process (`python_supervisor`)
//!  - Expose a tiny loopback HTTP server for secret handshake +
//!    shell-approval bridge (`bridge`)
//!  - Own the Windows Credential Manager-backed key vault (`secrets`)
//!  - Own the system tray + main window
//!  - Wait for Python's port handshake (embedded Hermes serves on loopback; the shell can open it in the system browser)
//!
//! All business logic lives in Python. This crate is a thin process
//! supervisor + secret/safety boundary.

mod approval;
mod bridge;
mod capture;
mod chat;
mod companion;
mod cron;
mod desktop_organizer;
mod dingtalk_env;
mod edge_browser;
mod email_env;
mod email_oauth;
mod gateway_env_patch;
mod gateway_supervisor;
mod legacy_upgrade;
mod pairing;
mod paths;
mod python_supervisor;
mod qq_env;
mod qqbot_qr;
mod secrets;
mod studio;
mod study;
mod telegram_env;
mod tray;
mod validation;
mod weixin_qr;
#[cfg(windows)]
mod windows_notification;

use serde::Serialize;
use std::collections::HashSet;
use std::sync::Arc;
use std::time::Duration;
use tauri::{Manager, RunEvent};
use tokio::sync::Mutex;
/// Fallback ``taskkill`` when the supervisor mutex is contended and
/// ``try_lock`` cannot acquire it at shutdown.
fn _emergency_kill_python_child(pid: Option<u32>) {
    if let Some(id) = pid {
        let _ = std::process::Command::new("taskkill")
            .args(&["/f", "/pid", &id.to_string()])
            .status();
    }
}

pub struct AppState {
    /// Edge CDP browser instance for browser automation (Windows only).
    pub edge_browser: Arc<crate::edge_browser::EdgeSupervisor>,
    pub supervisor: Arc<Mutex<Option<python_supervisor::Supervisor>>>,
    /// Optional ``kabuqina gateway run`` child (messaging adapters).
    pub gateway_supervisor: Arc<Mutex<Option<gateway_supervisor::GatewaySupervisor>>>,
    /// Optional Weixin QR login child (`weixin_qr_worker.py`); separate from the long-lived Hermes process.
    pub weixin_qr_child: Arc<Mutex<Option<tokio::process::Child>>>,
    /// Optional QQ Bot QR login child (`qqbot_qr_worker.py`); separate from the long-lived Hermes process.
    pub qqbot_qr_child: Arc<Mutex<Option<tokio::process::Child>>>,
    pub bridge_addr: Arc<Mutex<Option<std::net::SocketAddr>>>,
    /// Cached from `bridge::Bridge` for respawning Python without a second `bridge::spawn`.
    pub bridge_secret_url: Arc<Mutex<Option<String>>>,
    pub bridge_approval_url: Arc<Mutex<Option<String>>>,
    pub bridge_desktop_delivery_url: Arc<Mutex<Option<String>>>,
    /// Pending desktop delivery messages (Python cron → frontend).
    pub desktop_messages: Arc<tokio::sync::Mutex<Vec<bridge::DesktopMessage>>>,
    /// Shell / messaging / cron approval requests awaiting webview response.
    pub approval_store: Arc<approval::ApprovalStore>,
    /// Loopback port for Hermes `web_server` (set after Python writes `port.txt`).
    pub hermes_port: Arc<Mutex<Option<u16>>>,
    /// Set when embedded Python fails to start (shown in shell /chat instead of spinning forever).
    pub hermes_bootstrap_error: Arc<Mutex<Option<String>>>,
    /// Same value as Python `KABUQINA_BRIDGE_SECRET` for `X-Kabuqina-Auth`.
    pub desk_auth_token: Arc<Mutex<Option<String>>>,
    /// Last known PID of the Python child for emergency kill.
    pub python_child_pid: Arc<std::sync::Mutex<Option<u32>>>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let supervisor = Arc::new(Mutex::new(None));
    let bridge_addr = Arc::new(Mutex::new(None));
    let edge_browser = Arc::new(crate::edge_browser::EdgeSupervisor::new());

    let approval_store = approval::ApprovalStore::new();

    let state = AppState {
        edge_browser: edge_browser.clone(),
        supervisor: supervisor.clone(),
        gateway_supervisor: Arc::new(Mutex::new(None)),
        weixin_qr_child: Arc::new(Mutex::new(None)),
        qqbot_qr_child: Arc::new(Mutex::new(None)),
        bridge_addr: bridge_addr.clone(),
        bridge_secret_url: Arc::new(Mutex::new(None)),
        bridge_approval_url: Arc::new(Mutex::new(None)),
        bridge_desktop_delivery_url: Arc::new(Mutex::new(None)),
        desktop_messages: Arc::new(tokio::sync::Mutex::new(Vec::new())),
        approval_store: approval_store.clone(),
        hermes_port: Arc::new(Mutex::new(None)),
        hermes_bootstrap_error: Arc::new(Mutex::new(None)),
        desk_auth_token: Arc::new(Mutex::new(None)),
        python_child_pid: Arc::new(std::sync::Mutex::new(None)),
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _argv, _cwd| {
            crate::companion::focus_main_window(app);
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_os::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .manage(state)
        .manage(capture::CaptureState::default())
        .invoke_handler(tauri::generate_handler![
            secrets::cmd_save_secret,
            secrets::cmd_has_secret,
            secrets::cmd_llm_config_preview,
            secrets::cmd_update_llm_config,
            secrets::cmd_clear_secret,
            secrets::cmd_validate_endpoint,
            python_supervisor::cmd_python_status,
            paths::cmd_workspace_path,
            paths::cmd_product_profile_contract,
            paths::cmd_open_workspace,
            paths::cmd_open_path,
            paths::cmd_reveal_path,
            cmd_set_workspace,
            paths::cmd_get_power_user,
            cmd_set_power_user,
            paths::cmd_set_personality,
            paths::cmd_get_auto_start_gateway,
            paths::cmd_set_auto_start_gateway,
            paths::cmd_read_shared_prefs,
            paths::cmd_write_text_file,
            paths::cmd_write_pdf_from_html,
            paths::cmd_save_shared_prefs,
            cmd_gateway_status,
            cmd_gateway_start,
            cmd_gateway_stop,
            cmd_get_kabuqina_port,
            cmd_get_kabuqina_bootstrap_error,
            chat::cmd_get_kabuqina_boot_state,
            companion::cmd_show_companion,
            companion::cmd_hide_companion,
            companion::cmd_resize_companion,
            companion::cmd_ensure_companion_position,
            companion::cmd_focus_main_window,
            desktop_organizer::cmd_desktop_organize_run,
            desktop_organizer::cmd_desktop_organize_preview,
            desktop_organizer::cmd_desktop_organize_apply,
            desktop_organizer::cmd_desktop_organize_undo,
            chat::cmd_chat_send,
            chat::cmd_chat_send_stream,
            chat::cmd_chat_preview,
            chat::cmd_desk_stop,
            chat::cmd_interaction_response,
            chat::cmd_get_sessions,
            chat::cmd_get_session_messages,
            chat::cmd_delete_session,
            chat::cmd_transcribe,
            chat::cmd_save_voice_setup,
            chat::cmd_stt_model_status,
            chat::cmd_stt_model_download,
            chat::cmd_load_packages,
            chat::cmd_load_package_download,
            chat::cmd_load_package_delete,
            chat::cmd_tts_speak,
            weixin_qr::cmd_weixin_qr_start,
            weixin_qr::cmd_weixin_qr_status,
            weixin_qr::cmd_weixin_env_status,
            qq_env::cmd_qq_env_status,
            telegram_env::cmd_telegram_env_status,
            telegram_env::cmd_telegram_save_token,
            telegram_env::cmd_telegram_remove_config,
            weixin_qr::cmd_weixin_env_remove,
            qq_env::cmd_qq_env_remove,
            dingtalk_env::cmd_dingtalk_env_status,
            dingtalk_env::cmd_dingtalk_env_remove,
            dingtalk_env::cmd_dingtalk_save_config,
            email_env::cmd_email_env_status,
            email_env::cmd_email_save_config,
            email_env::cmd_email_env_remove,
            email_oauth::cmd_email_oauth_status,
            email_oauth::cmd_email_oauth_device_start,
            email_oauth::cmd_email_oauth_device_finish,
            weixin_qr::cmd_weixin_qr_cancel,
            weixin_qr::cmd_restart_embedded_hermes,
            qqbot_qr::cmd_qqbot_qr_start,
            qqbot_qr::cmd_qqbot_qr_status,
            qqbot_qr::cmd_qqbot_qr_cancel,
            gateway_env_patch::cmd_gateway_host_env_get,
            gateway_env_patch::cmd_gateway_host_env_patch,
            legacy_upgrade::cmd_legacy_channel_inventory,
            legacy_upgrade::cmd_legacy_channel_export,
            legacy_upgrade::cmd_legacy_channel_cleanup,
            pairing::cmd_pairing_list,
            pairing::cmd_pairing_approve,
            pairing::cmd_pairing_revoke,
            pairing::cmd_pairing_clear_pending,
            cmd_desktop_messages,
            approval::cmd_respond_approval,
            cron::cmd_cron_list,
            cron::cmd_cron_toggle,
            cron::cmd_cron_delete,
            cron::cmd_goal_create,
            cron::cmd_goal_pause,
            cron::cmd_goal_resume,
            cron::cmd_goal_cancel,
            cron::cmd_goal_delete,
            study::cmd_study_spaces,
            study::cmd_study_space_create,
            study::cmd_study_space_select,
            study::cmd_study_scratch_get,
            study::cmd_study_scratch_save_pad,
            study::cmd_study_scratch_file_note,
            studio::cmd_studio_projects,
            studio::cmd_studio_create_project,
            studio::cmd_studio_save_brief,
            studio::cmd_studio_delete_project,
            studio::cmd_studio_gather_sources,
            study::cmd_study_drafts,
            study::cmd_study_artifact_summaries,
            study::cmd_study_artifact_detail,
            study::cmd_study_artifact_status,
            study::cmd_study_artifact_source_audit,
            study::cmd_study_artifact_semantic_review,
            study::cmd_study_knowledge_points,
            study::cmd_study_wrongbook,
            study::cmd_study_activities,
            study::cmd_study_activity_start,
            study::cmd_study_activity_get,
            study::cmd_study_activity_list,
            study::cmd_study_activity_resume,
            study::cmd_study_activity_cancel,
            study::cmd_study_tutor_whiteboard_preview,
            study::cmd_study_tutor_whiteboard_apply,
            study::cmd_study_tutor_whiteboard_snapshot,
            study::cmd_study_tutor_whiteboard_attach,
            study::cmd_study_tutor_whiteboard_recover,
            study::cmd_study_tutor_whiteboard_cancel,
            study::cmd_study_whiteboards,
            study::cmd_study_whiteboard_working_get,
            study::cmd_study_whiteboard_working_save,
            study::cmd_study_whiteboard_working_delete,
            study::cmd_study_whiteboard_snapshots,
            study::cmd_study_whiteboard_snapshot_create,
            study::cmd_study_whiteboard_snapshot_get,
            study::cmd_study_whiteboard_snapshot_restore,
            study::cmd_study_whiteboard_snapshot_attach,
            study::cmd_study_whiteboard_snapshot_export,
            study::cmd_study_whiteboard_snapshot_delete_preview,
            study::cmd_study_whiteboard_snapshot_delete,
            study::cmd_study_data_export,
            study::cmd_study_token_usage,
            study::cmd_study_preferences_get,
            study::cmd_study_preferences_put,
            study::cmd_study_material_read,
            study::cmd_study_data_import,
            study::cmd_study_data_import_file,
            study::cmd_study_prepare_downgrade,
            study::cmd_study_data_delete,
            study::cmd_study_migration_status,
            study::cmd_study_migration_failures_export,
            study::cmd_study_student_state_get,
            study::cmd_study_student_state_put,
            study::cmd_study_migrate_context,
            study::cmd_study_evaluations,
            study::cmd_study_evaluation_detail,
            study::cmd_study_learning_plans,
            study::cmd_study_plan_items,
            study::cmd_study_plan_item_complete,
            study::cmd_study_plan_item_skip,
            study::cmd_study_review_reminder_get,
            study::cmd_study_review_reminder_put,
            study::cmd_study_artifact_activate,
            study::cmd_study_artifact_reject,
            study::cmd_study_flashcards,
            study::cmd_study_flashcard_capture,
            study::cmd_study_flashcard_review,
            study::cmd_study_migrate_flashcards,
            study::cmd_study_quizzes,
            study::cmd_study_quiz_questions,
            study::cmd_study_quiz_submit,
            study::cmd_study_quiz_generate_practice,
            study::cmd_study_practice_hint,
            study::cmd_study_practice_source,
            study::cmd_study_migrate_quizzes,
            study::cmd_study_migrate_builtin_course,
            capture::cmd_capture_region,
            capture::cmd_capture_fullscreen,
            capture::cmd_show_capture_overlay,
            capture::cmd_hide_capture_overlay,
        ])
        .setup(|app| {
            #[cfg(windows)]
            windows_notification::init();
            tray::install_main_close_hides_to_tray(app)?;
            tray::install(app)?;
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = bootstrap(handle).await {
                    log::error!("bootstrap failed: {e:#}");
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error building Kabuqina")
        .run(|app, event| {
            if let RunEvent::ExitRequested { .. } = &event {
                // Clone `Arc`s then drop `State` so `try_lock` temporaries never borrow `state`
                // across the end of the block (E0597 with nested `if let` + `try_lock`).
                let state: tauri::State<AppState> = app.state();
                let edge = state.edge_browser.clone();
                let supervisor = state.supervisor.clone();
                let gateway = state.gateway_supervisor.clone();
                let weixin_qr = state.weixin_qr_child.clone();
                let qqbot_qr = state.qqbot_qr_child.clone();
                let last_pid = state.python_child_pid.lock().ok().and_then(|g| *g);
                std::mem::drop(state);
                let sup_lock = supervisor.try_lock();
                if let Ok(mut sup) = sup_lock {
                    if let Some(s) = sup.take() {
                        let _ = s.shutdown();
                    }
                } else {
                    _emergency_kill_python_child(last_pid);
                }
                let gw_lock = gateway.try_lock();
                if let Ok(mut gw) = gw_lock {
                    if let Some(g) = gw.take() {
                        let _ = g.shutdown();
                    }
                }
                let wq_lock = weixin_qr.try_lock();
                if let Ok(mut wq) = wq_lock {
                    if let Some(mut c) = wq.take() {
                        let _ = c.start_kill();
                    }
                }
                let qq_lock = qqbot_qr.try_lock();
                if let Ok(mut qq) = qq_lock {
                    if let Some(mut c) = qq.take() {
                        let _ = c.start_kill();
                    }
                }
                // Kill Edge CDP browser instance.
                edge.stop();
            }
        });
}

async fn resolve_spawn_config_for_children(
    app: &tauri::AppHandle,
) -> Result<python_supervisor::SpawnConfig, String> {
    let state: tauri::State<'_, AppState> = app.state();
    let secret_url = state
        .bridge_secret_url
        .lock()
        .await
        .clone()
        .ok_or_else(|| "bridge not initialised (secret URL)".to_string())?;
    let approval_url = state
        .bridge_approval_url
        .lock()
        .await
        .clone()
        .ok_or_else(|| "bridge not initialised (approval URL)".to_string())?;
    let desktop_delivery_url = state
        .bridge_desktop_delivery_url
        .lock()
        .await
        .clone()
        .ok_or_else(|| "bridge not initialised (desktop delivery URL)".to_string())?;
    let desk_token = state
        .desk_auth_token
        .lock()
        .await
        .clone()
        .ok_or_else(|| "bridge not initialised (token)".to_string())?;
    let baddr = *state
        .bridge_addr
        .lock()
        .await
        .as_ref()
        .ok_or_else(|| "bridge not initialised (addr)".to_string())?;

    let workspace = paths::ensure_workspace(app).map_err(|e| e.to_string())?;
    let bundle_dir = paths::resolve_runtime_dir(app).map_err(|e| e.to_string())?;
    let data_dir = paths::ensure_data_dir(app).map_err(|e| e.to_string())?;
    let kabuqina_home = gateway_supervisor::kabuqina_home_path(&data_dir);
    let llm = secrets::resolve_llm_spawn_params(app);
    let power_user = paths::is_power_user(app);
    let shell_chat_back_url = format!(
        "http://127.0.0.1:{}/shell-chat/{}",
        baddr.port(),
        desk_token
    );

    // Fetch the API key and determine the correct env var name.
    let (api_key, api_key_env_name) = secrets::read_current_secret(app)
        .map(|key| {
            let env_name = secrets::provider_api_key_env(&llm.provider);
            (Some(key), env_name)
        })
        .unwrap_or((None, String::new()));

    Ok(python_supervisor::SpawnConfig {
        bundle_dir,
        data_dir,
        kabuqina_home,
        workspace,
        secret_url,
        approval_url,
        desktop_delivery_url,
        desk_auth_token: desk_token,
        shell_chat_back_url,
        provider: llm.provider,
        llm_host: llm.llm_host,
        api_base_url: llm.api_base_url,
        api_mode: llm.api_mode,
        hermes_model: llm.hermes_model,
        inference_provider: llm.inference_provider,
        power_user,
        product_profile: paths::resolve_product_profile(app),
        api_key,
        api_key_env_name,
    })
}

async fn stop_gateway_service(app: &tauri::AppHandle) {
    let state: tauri::State<AppState> = app.state();
    let mut g = state.gateway_supervisor.lock().await;
    if let Some(gw) = g.take() {
        let _ = gw.shutdown().await;
    }
    drop(g);

    // Clean up stale gateway state files per profile.
    let data_dir = match paths::ensure_data_dir(app) {
        Ok(d) => d,
        Err(_) => return,
    };
    let host_home = gateway_supervisor::kabuqina_home_path(&data_dir);
    let profiles_dir = host_home.join("profiles");
    if let Ok(entries) = std::fs::read_dir(&profiles_dir) {
        for entry in entries.flatten() {
            let p = entry.path();
            if p.is_dir() {
                for name in &["gateway.lock", "gateway.pid", "gateway_state.json"] {
                    let _ = std::fs::remove_file(p.join(name));
                }
            }
        }
    }
}

async fn maybe_auto_start_gateway_service(
    app: &tauri::AppHandle,
    cfg: &python_supervisor::SpawnConfig,
) {
    if !paths::is_auto_start_gateway(app) {
        return;
    }
    let hh = gateway_supervisor::kabuqina_home_path(&cfg.data_dir);
    if !gateway_supervisor::dotenv_suggests_messaging_gateway(&hh, &cfg.product_profile) {
        return;
    }
    let state: tauri::State<AppState> = app.state();
    let mut lock = state.gateway_supervisor.lock().await;
    if let Some(mut existing) = lock.take() {
        if existing.any_running() {
            *lock = Some(existing);
            log::info!("messaging gateway already running; skip auto-start");
            return;
        }
        let _ = existing.shutdown();
    }
    drop(lock);
    match gateway_supervisor::GatewaySupervisor::spawn_all(cfg).await {
        Ok(gw) => {
            log::info!(
                "messaging gateway started (auto): {} platform(s)",
                gw.platform_count()
            );
            let state: tauri::State<AppState> = app.state();
            *state.gateway_supervisor.lock().await = Some(gw);
        }
        Err(e) => log::warn!("messaging gateway auto-start failed: {e:#}"),
    }
}

fn should_start_gateway_after_hermes_respawn() -> bool {
    false
}

/// Gateway startup is manual-only. Embedded Hermes restarts (e.g. settings
/// changes or QR credential saves) should not start messaging platform pollers.
async fn ensure_gateway_after_hermes_respawn(
    app: &tauri::AppHandle,
    cfg: &python_supervisor::SpawnConfig,
) {
    if !should_start_gateway_after_hermes_respawn() {
        log::info!("messaging gateway remains stopped after Hermes respawn (manual start only)");
        return;
    }
    let hh = gateway_supervisor::kabuqina_home_path(&cfg.data_dir);
    if !gateway_supervisor::dotenv_suggests_messaging_gateway(&hh, &cfg.product_profile) {
        return;
    }
    match gateway_supervisor::GatewaySupervisor::spawn_all(cfg).await {
        Ok(gw) => {
            log::info!(
                "messaging gateway started after Hermes respawn: {} platform(s)",
                gw.platform_count()
            );
            let state: tauri::State<AppState> = app.state();
            *state.gateway_supervisor.lock().await = Some(gw);
        }
        Err(e) => log::warn!("messaging gateway start after Hermes respawn failed: {e:#}"),
    }
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PlatformStatus {
    pub platform: String,
    pub running: bool,
    pub disk_gateway_state: Option<String>,
    pub disk_exit_reason: Option<String>,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct GatewayStatusPayload {
    pub running: bool,
    pub eligible: bool,
    /// Bundled ``hermes/gateway/run.py`` includes first-connect survival (post build_bundle).
    pub embedded_gateway_startup_survival: bool,
    /// Per-platform status.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub per_platform: Vec<PlatformStatus>,
}

#[tauri::command]
async fn cmd_gateway_status(app: tauri::AppHandle) -> Result<GatewayStatusPayload, String> {
    let data_dir = paths::ensure_data_dir(&app).map_err(|e| e.to_string())?;
    let hh = gateway_supervisor::kabuqina_home_path(&data_dir);
    let product_profile = paths::resolve_product_profile(&app);
    let eligible = gateway_supervisor::dotenv_suggests_messaging_gateway(&hh, &product_profile);

    let embedded_gateway_startup_survival = match resolve_spawn_config_for_children(&app).await {
        Ok(cfg) => gateway_supervisor::bundled_gateway_has_startup_survival(&cfg.bundle_dir),
        Err(_) => false,
    };

    let state: tauri::State<AppState> = app.state();
    let mut g = state.gateway_supervisor.lock().await;

    // Reap any exited children and collect per-platform running state.
    let mut per_platform: Vec<PlatformStatus> = Vec::new();
    let mut running = false;

    if let Some(gw) = g.as_mut() {
        // Collect running platforms before reaping.
        let running_set: HashSet<String> = gw.running_map().into_keys().collect();

        // Read per-profile state files for each known platform.
        let configured = gateway_supervisor::discover_configured_platforms(
            &gateway_supervisor::parse_dotenv_upper(&hh),
            &product_profile,
        );
        for platform in &configured {
            let profile_home = gateway_supervisor::profile_home_path(&data_dir, platform);
            let (state_str, exit_reason) =
                gateway_supervisor::read_gateway_state_snapshot(&profile_home);
            let is_running = running_set.contains(platform.as_str());
            if is_running {
                running = true;
            }
            per_platform.push(PlatformStatus {
                platform: platform.clone(),
                running: is_running,
                disk_gateway_state: state_str,
                disk_exit_reason: exit_reason,
            });
        }

        // Reap so stale children don't accumulate.
        gw.reap_exited();
    }

    Ok(GatewayStatusPayload {
        running,
        eligible,
        embedded_gateway_startup_survival,
        per_platform,
    })
}

#[tauri::command]
async fn cmd_gateway_start(app: tauri::AppHandle) -> Result<(), String> {
    let cfg = resolve_spawn_config_for_children(&app).await?;
    let hh = gateway_supervisor::kabuqina_home_path(&cfg.data_dir);
    if !gateway_supervisor::dotenv_suggests_messaging_gateway(&hh, &cfg.product_profile) {
        return Err(
            "No messaging credentials found in kabuqina-home/.env. Open Keys in Kabuqina and save tokens first."
                .into(),
        );
    }
    stop_gateway_service(&app).await;
    // Ensure migration first.
    gateway_supervisor::ensure_migration(&cfg.data_dir, &cfg.product_profile)
        .map_err(|e| format!("migration failed: {e}"))?;
    let gw = gateway_supervisor::GatewaySupervisor::spawn_all(&cfg)
        .await
        .map_err(|e| e.to_string())?;
    let platform_count = gw.platform_count();
    let state: tauri::State<AppState> = app.state();
    *state.gateway_supervisor.lock().await = Some(gw);
    // Detect immediate crash (e.g. all platform children died at startup).
    tokio::time::sleep(Duration::from_secs(2)).await;
    let state: tauri::State<AppState> = app.state();
    let mut lock = state.gateway_supervisor.lock().await;
    if let Some(mut gw) = lock.take() {
        if gw.any_running() {
            *lock = Some(gw);
            log::info!(
                "messaging gateway still running after manual start ({platform_count} platform(s))"
            );
            return Ok(());
        }
        // All children exited — collect diagnostics.
        let stderr = gw.aggregate_stderr();
        let mut parts = vec!["All gateway platforms exited during startup.".to_string()];
        for (platform, status) in gw.reap_exited() {
            let profile_home = gateway_supervisor::profile_home_path(&cfg.data_dir, &platform);
            let (_, exit_reason) = gateway_supervisor::read_gateway_state_snapshot(&profile_home);
            let log_tail = gateway_supervisor::tail_gateway_log(&profile_home, 4096);
            let mut per = vec![format!("[{}] exit code {}", platform, status)];
            if let Some(r) = exit_reason.as_ref().filter(|s| !s.is_empty()) {
                per.push(format!("recorded: {r}"));
            }
            if let Some(t) = log_tail {
                per.push(format!("gateway.log (tail): {t}"));
            }
            parts.push(per.join(" | "));
        }
        if !stderr.is_empty() {
            const MAX: usize = 2000;
            let capped: String = if stderr.chars().count() > MAX {
                let trunc: String = stderr.chars().take(MAX).collect();
                format!("{trunc}…")
            } else {
                stderr.to_string()
            };
            parts.push(format!("stderr (captured): {capped}"));
        }
        parts.push(
            "If this persists: run python/build_bundle.ps1 so kabuqina-home picks up the latest gateway (first-connect retry fix), then relaunch Kabuqina."
                .into(),
        );
        if !gateway_supervisor::bundled_gateway_has_startup_survival(&cfg.bundle_dir) {
            parts.push(
                "Detected: the embedded runtime's hermes/gateway/run.py does NOT include the first-connect survival patch — your bundle is almost certainly stale. Close Kabuqina, run python/build_bundle.ps1 from the repo root, then relaunch (a dev build must use the refreshed python/dist/runtime)."
                    .into(),
            );
        }
        return Err(parts.join(" "));
    }
    Ok(())
}

#[tauri::command]
async fn cmd_gateway_stop(app: tauri::AppHandle) -> Result<(), String> {
    stop_gateway_service(&app).await;
    Ok(())
}

async fn bootstrap(app: tauri::AppHandle) -> anyhow::Result<()> {
    let boot_t0 = std::time::Instant::now();
    let reveal_main = || {
        if let Some(w) = app.get_webview_window("main") {
            let _ = w.show();
            let _ = w.set_focus();
        }
    };

    // 1. Workspace + data dirs (spawn config resolves paths again).
    if let Err(e) = (|| -> anyhow::Result<()> {
        paths::ensure_workspace(&app)?;
        let data_dir = paths::ensure_data_dir(&app)?;
        // Freeze the host-home decision before Edge or any Python/QR child can
        // start. Later callers only read the process cache and propagate this
        // exact path through SpawnConfig/child env.
        let _selected_home = gateway_supervisor::kabuqina_home_path(&data_dir);
        paths::resolve_runtime_dir(&app)?;
        Ok(())
    })() {
        let msg = format!("{e:#}");
        log::error!("bootstrap setup failed (before Python): {msg}");
        *app.state::<AppState>().hermes_bootstrap_error.lock().await = Some(msg);
        reveal_main();
        capture::register_global_shortcut(&app);
        return Ok(());
    }

    log::info!("bootstrap setup_ms={}", boot_t0.elapsed().as_millis());

    // 2. Stand up the loopback bridge (secret handshake + shell approval + desktop delivery).
    let (desktop_q, approval_store) = {
        let state: tauri::State<AppState> = app.state();
        (state.desktop_messages.clone(), state.approval_store.clone())
    };
    let bridge_t0 = std::time::Instant::now();
    let bridge_ok = bridge::spawn(app.clone(), desktop_q, approval_store).await;
    log::info!("bootstrap bridge_ms={}", bridge_t0.elapsed().as_millis());
    if let Err(e) = bridge_ok {
        let msg = format!("{e:#}");
        log::error!("loopback bridge failed: {msg}");
        *app.state::<AppState>().hermes_bootstrap_error.lock().await = Some(msg);
        capture::register_global_shortcut(&app);
        return Ok(());
    }
    let bridge = bridge_ok.unwrap();
    {
        let state: tauri::State<AppState> = app.state();
        *state.bridge_addr.lock().await = Some(bridge.addr);
        *state.desk_auth_token.lock().await = Some(bridge.desk_auth_token.clone());
        *state.bridge_secret_url.lock().await = Some(bridge.secret_url.clone());
        *state.bridge_approval_url.lock().await = Some(bridge.approval_url.clone());
        *state.bridge_desktop_delivery_url.lock().await = Some(bridge.desktop_delivery_url.clone());
    }

    // 2a. Start Edge CDP browser in the background — must not block Python spawn.
    {
        let edge_app = app.clone();
        tauri::async_runtime::spawn(async move {
            let edge_t0 = std::time::Instant::now();
            let state: tauri::State<AppState> = edge_app.state();
            let data_dir = match crate::paths::ensure_data_dir(&edge_app) {
                Ok(d) => d,
                Err(e) => {
                    log::warn!("Edge browser start skipped (data dir): {e}");
                    return;
                }
            };
            if let Err(e) = state.edge_browser.start(&data_dir) {
                log::warn!("Edge browser start skipped (browser tool will be unavailable): {e}");
            } else {
                log::info!("bootstrap edge_ms={}", edge_t0.elapsed().as_millis());
            }
        });
    }

    // 3. Spawn the Python child (Hermes web_server / desktop_entrypoint).
    //    Errors here are logged but do NOT block the window from showing,
    //    so the user can see the shell UI and diagnose startup issues.
    let hermes_ok = async {
        let python_t0 = std::time::Instant::now();
        let spawn_cfg = resolve_spawn_config_for_children(&app)
            .await
            .map_err(|e| anyhow::anyhow!(e))?;
        let supervisor = python_supervisor::Supervisor::spawn(spawn_cfg.clone()).await?;
        log::info!(
            "bootstrap python_spawn_ms={}",
            python_t0.elapsed().as_millis()
        );

        let port_wait_t0 = std::time::Instant::now();
        let port = supervisor.wait_for_port().await?;
        log::info!(
            "python ready on port {port} (bootstrap port_wait_ms={})",
            port_wait_t0.elapsed().as_millis()
        );

        {
            let state: tauri::State<AppState> = app.state();
            if let Ok(mut pid_guard) = state.python_child_pid.lock() {
                *pid_guard = supervisor.pid;
            }
            *state.supervisor.lock().await = Some(supervisor);
            *state.hermes_port.lock().await = Some(port);
        }

        maybe_auto_start_gateway_service(&app, &spawn_cfg).await;
        anyhow::Result::<()>::Ok(())
    }
    .await;

    match hermes_ok {
        Ok(()) => {
            log::info!("Hermes Python bootstrap complete");
            *app.state::<AppState>().hermes_bootstrap_error.lock().await = None;
        }
        Err(e) => {
            let msg = format!("{e:#}");
            log::error!("Hermes Python bootstrap failed: {msg}");
            *app.state::<AppState>().hermes_bootstrap_error.lock().await = Some(msg);
        }
    }

    // 4. Register global screenshot shortcut (Ctrl+Alt+A).
    capture::register_global_shortcut(&app);

    // On success the frontend reveals the window via showMainWindowWhenReady()
    // after its first render (avoids a blank webview flash). Rust only force-shows
    // the window as a bootstrap-failure fallback (see the error paths above).

    log::info!("bootstrap total_ms={}", boot_t0.elapsed().as_millis());
    Ok(())
}

/// Re-spawn the Hermes child so `HERMESDESK_POWER_USER` and
/// `default_toolset.install()` take effect. Tooling is re-seeded on every
/// Python start; a simple settings write does not update the child.
pub(crate) async fn respawn_embedded_hermes_python(app: tauri::AppHandle) -> Result<u16, String> {
    let state: tauri::State<'_, AppState> = app.state();
    stop_gateway_service(&app).await;

    {
        let mut s = state.supervisor.lock().await;
        if let Some(sup) = s.take() {
            let _ = sup.shutdown();
        }
    }
    *state.hermes_port.lock().await = None;

    let spawn_cfg = resolve_spawn_config_for_children(&app).await?;
    let power_user = spawn_cfg.power_user;
    let supervisor = python_supervisor::Supervisor::spawn(spawn_cfg.clone())
        .await
        .map_err(|e| e.to_string())?;
    let port = supervisor
        .wait_for_port()
        .await
        .map_err(|e| e.to_string())?;
    if let Ok(mut pid_guard) = state.python_child_pid.lock() {
        *pid_guard = supervisor.pid;
    }
    *state.supervisor.lock().await = Some(supervisor);
    *state.hermes_port.lock().await = Some(port);
    *state.hermes_bootstrap_error.lock().await = None;
    log::info!("embedded Python respawned: port {port} power_user={power_user}");
    ensure_gateway_after_hermes_respawn(&app, &spawn_cfg).await;
    Ok(port)
}

pub(crate) fn schedule_embedded_hermes_respawn(app: tauri::AppHandle) {
    tauri::async_runtime::spawn(async move {
        if let Err(e) = respawn_embedded_hermes_python(app.clone()).await {
            log::error!("embedded Python background respawn failed: {e}");
            let state: tauri::State<AppState> = app.state();
            *state.hermes_bootstrap_error.lock().await = Some(e);
        }
    });
}

/// Save the power-user flag and restart embedded Python so
/// `platform_toolsets[cli]` matches the toggle (terminal, browser, …).
#[tauri::command]
async fn cmd_set_power_user(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    paths::set_power_user_enabled(&app, enabled)?;
    respawn_embedded_hermes_python(app).await.map(|_| ())
}

/// Persist a custom workspace path and restart embedded Python so the workspace
/// environment variables used by Hermes and gateway children are refreshed.
#[tauri::command]
async fn cmd_set_workspace(
    app: tauri::AppHandle,
    path: String,
    migrate_files: bool,
) -> Result<paths::WorkspaceUpdateResult, String> {
    let result = paths::set_workspace_path(&app, path, migrate_files)?;
    respawn_embedded_hermes_python(app).await?;
    Ok(result)
}

/// Get the Kabuqina Python backend port (for diagnostics and fallbacks).
#[tauri::command]
async fn cmd_get_kabuqina_port(app: tauri::AppHandle) -> Result<Option<u16>, String> {
    let state: tauri::State<AppState> = app.state();
    let port = *state.hermes_port.lock().await;
    Ok(port)
}

/// Why embedded Python did not become ready (missing runtime, overlay crash, …).
#[tauri::command]
async fn cmd_get_kabuqina_bootstrap_error(app: tauri::AppHandle) -> Result<Option<String>, String> {
    let state: tauri::State<AppState> = app.state();
    let err = state.hermes_bootstrap_error.lock().await.clone();
    Ok(err)
}

/// Return pending desktop delivery messages (from Python cron/send_message)
/// and clear the buffer.  The frontend polls this periodically.
#[tauri::command]
async fn cmd_desktop_messages(
    app: tauri::AppHandle,
) -> Result<Vec<bridge::DesktopMessage>, String> {
    let state: tauri::State<AppState> = app.state();
    let mut msgs = state.desktop_messages.lock().await;
    let drained = std::mem::take(&mut *msgs);
    Ok(drained)
}

#[cfg(test)]
mod tests {
    use super::should_start_gateway_after_hermes_respawn;

    #[test]
    fn hermes_respawn_keeps_gateway_manual_start_only() {
        assert!(!should_start_gateway_after_hermes_respawn());
    }
}
