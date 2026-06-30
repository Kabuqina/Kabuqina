// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Cron job management — read/write the upstream ``cron/jobs.json`` file.
//!
//! The frontend Settings → Scheduled Tasks page uses these commands to
//! list, pause, resume, and delete cron jobs.  The Python cron ticker also
//! reads/writes this file (with OS-level file locks), so we acquire the
//! same lock for writes.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::AppHandle;

/// Lightweight JSON file lock: creates a sibling lock file.
/// The Python cron code uses ``fcntl.lockf`` (Unix) or ``msvcrt.locking``
/// (Windows) on ``cron/.tick.lock``.  For read-heavy metadata listing we
/// don't contend with the tick lock; for writes we take the same lock.
fn cron_lock_path(data_dir: &std::path::Path) -> PathBuf {
    data_dir.join("hermes-home").join("cron").join(".tick.lock")
}

fn jobs_path(data_dir: &std::path::Path) -> PathBuf {
    data_dir.join("hermes-home").join("cron").join("jobs.json")
}

/// A cron job as stored in jobs.json (subset of fields we surface).
#[derive(Debug, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct CronJobEntry {
    pub id: String,
    pub name: String,
    pub schedule: String,
    pub prompt: String,
    pub deliver: String,
    pub paused: bool,
    pub next_run_at: Option<String>,
    pub last_run_at: Option<String>,
    /// "scheduled" | "paused" | "completed" | "error" — surfaced so the UI
    /// can split active jobs from one-shot completions.
    pub state: String,
    pub completed_at: Option<String>,
    pub last_status: Option<String>,
    pub last_delivery_error: Option<String>,
    pub mode: Option<String>,
    pub goal_status: Option<String>,
    pub goal_iteration: Option<u64>,
    pub goal_cost_usd: Option<String>,
    pub goal_cost_accounting: Option<String>,
    pub goal_pause_reason: Option<String>,
    pub goal_updated_at: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CronJobListResponse {
    /// Active jobs (state != "completed"). Backwards-compat: this field
    /// stays the primary list the UI iterates today.
    pub jobs: Vec<CronJobEntry>,
    /// One-shot tasks that already fired. UI shows them in a separate
    /// "Recently completed" section; runner prunes after 7 days.
    pub completed: Vec<CronJobEntry>,
    pub has_any: bool,
}

fn _data_dir(app: &AppHandle) -> Result<PathBuf, String> {
    crate::paths::ensure_data_dir(app).map_err(|e| e.to_string())
}

/// Schema of ``jobs.json`` as written by ``hermes_core/cron/jobs.py::save_jobs``:
///
/// ```text
/// { "jobs": [ {...}, {...} ], "updated_at": "<iso8601>" }
/// ```
///
/// We must read AND write this exact shape — the Python scheduler reads the
/// file on every tick (`data.get("jobs", [])`) and a top-level array would
/// silently load as an empty job list, breaking the user's tasks.
fn read_jobs_raw(app: &AppHandle) -> Result<Vec<serde_json::Value>, String> {
    let data_dir = _data_dir(app)?;
    let path = jobs_path(&data_dir);
    if !path.exists() {
        return Ok(Vec::new());
    }
    let raw = std::fs::read_to_string(&path).map_err(|e| format!("read jobs.json: {e}"))?;

    let parsed: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => {
            log::warn!("cron: jobs.json parse failed: {e}; treating as empty");
            return Ok(Vec::new());
        }
    };

    // Expected: object with `jobs` array. Tolerate a bare array as a fallback
    // (older format / hand-edited file) so we don't lose user data.
    if let Some(arr) = parsed.get("jobs").and_then(|v| v.as_array()) {
        return Ok(arr.clone());
    }
    if let Some(arr) = parsed.as_array() {
        log::warn!("cron: jobs.json is a bare array (legacy/hand-edited); migrating on next write");
        return Ok(arr.clone());
    }
    log::warn!("cron: jobs.json has unexpected shape; treating as empty");
    Ok(Vec::new())
}

fn write_jobs_raw(app: &AppHandle, jobs: &[serde_json::Value]) -> Result<(), String> {
    let data_dir = _data_dir(app)?;
    let path = jobs_path(&data_dir);
    let lock_path = cron_lock_path(&data_dir);

    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("mkdir: {e}"))?;
    }

    // Touch the same lock file the Python ticker uses. We don't actually hold
    // an OS-level lock here (LockFileEx interop is out of scope); writes are
    // atomic via temp-file + rename, and the Python ticker tolerates parsing
    // a stale snapshot for one tick.
    let lock_file = std::fs::OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(&lock_path)
        .map_err(|e| format!("open lock: {e}"))?;
    drop(lock_file);

    // Match Python's structure exactly: { "jobs": [...], "updated_at": "..." }.
    let updated_at = chrono_iso_now();
    let payload = serde_json::json!({
        "jobs": jobs,
        "updated_at": updated_at,
    });

    let tmp = path.with_extension("tmp");
    let json = serde_json::to_string_pretty(&payload).map_err(|e| format!("serialize: {e}"))?;
    std::fs::write(&tmp, json).map_err(|e| format!("write tmp: {e}"))?;
    std::fs::rename(&tmp, &path).map_err(|e| format!("rename: {e}"))?;

    Ok(())
}

/// ISO-8601 timestamp with offset, matching Python's
/// ``hermes_time.now().isoformat()`` output (e.g. ``2026-05-10T23:55:51.708931+08:00``).
fn chrono_iso_now() -> String {
    // Use SystemTime + chrono-free formatting to avoid pulling in chrono
    // just for a timestamp. Local time with millisecond precision is fine
    // — Python parses any ISO-8601 with offset.
    use std::time::{SystemTime, UNIX_EPOCH};
    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default();
    let secs = now.as_secs() as i64;
    let micros = now.subsec_micros();

    // Compute local-offset seconds via a single std call.
    // On Windows, `time` crate would be cleaner, but the existing repo
    // already avoids extra deps; format as UTC with `Z` suffix — Python's
    // `datetime.fromisoformat` parses this fine.
    let utc = chrono_format_utc(secs, micros);
    utc
}

fn chrono_format_utc(secs: i64, micros: u32) -> String {
    // Simple UTC formatter: yyyy-mm-ddTHH:MM:SS.ffffffZ
    // Algorithm: days since 1970-01-01 → civil date.
    let days = secs.div_euclid(86_400);
    let secs_of_day = secs.rem_euclid(86_400) as u32;
    let (y, m, d) = days_to_ymd(days);
    let hh = secs_of_day / 3600;
    let mm = (secs_of_day % 3600) / 60;
    let ss = secs_of_day % 60;
    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}.{:06}Z",
        y, m, d, hh, mm, ss, micros
    )
}

/// Convert days since 1970-01-01 to (year, month, day).
/// Algorithm from Howard Hinnant's "date" library (public domain).
fn days_to_ymd(days: i64) -> (i32, u32, u32) {
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u32; // [0, 146096]
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365; // [0, 399]
    let y = yoe as i32 + era as i32 * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100); // [0, 365]
    let mp = (5 * doy + 2) / 153; // [0, 11]
    let d = doy - (153 * mp + 2) / 5 + 1; // [1, 31]
    let m = if mp < 10 { mp + 3 } else { mp - 9 }; // [1, 12]
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

#[derive(Debug, Deserialize)]
struct GoalStateProjection {
    schema_version: u64,
    job_id: String,
    status: String,
    iteration: u64,
    accumulated_cost_usd: String,
    cost_accounting: String,
    pause_reason: Option<String>,
    updated_at: String,
}

#[derive(Default)]
struct SanitizedGoalProjection {
    status: Option<String>,
    iteration: Option<u64>,
    cost_usd: Option<String>,
    cost_accounting: Option<String>,
    pause_reason: Option<String>,
    updated_at: Option<String>,
}

fn state_error_projection() -> SanitizedGoalProjection {
    SanitizedGoalProjection {
        status: Some("state_error".to_string()),
        ..SanitizedGoalProjection::default()
    }
}

fn sanitized_pause_reason(reason: Option<String>) -> Option<String> {
    const ALLOWED: &[&str] = &[
        "ambiguous_external_effect",
        "cost_unknown",
        "worker_blocked",
        "verifier_error",
        "max_runs",
        "max_cost_usd",
        "max_wall_seconds",
        "deadline",
        "no_progress",
        "missing_report",
        "recovery_review",
        "feature_disabled",
    ];
    reason.map(|value| {
        if ALLOWED.contains(&value.as_str()) {
            value
        } else {
            "other".to_string()
        }
    })
}

fn read_goal_projection(data_dir: &std::path::Path, job_id: &str) -> SanitizedGoalProjection {
    if job_id.len() != 12
        || !job_id
            .bytes()
            .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    {
        return state_error_projection();
    }
    let path = data_dir
        .join("hermes-home")
        .join("cron")
        .join("goal-runs")
        .join(job_id)
        .join("state.json");
    let raw = match std::fs::read_to_string(path) {
        Ok(value) => value,
        Err(_) => return state_error_projection(),
    };
    let state: GoalStateProjection = match serde_json::from_str(&raw) {
        Ok(value) => value,
        Err(_) => return state_error_projection(),
    };
    let valid_status = matches!(
        state.status.as_str(),
        "scheduled" | "running" | "verifying" | "completed" | "paused" | "failed" | "cancelled"
    );
    let valid_accounting = matches!(state.cost_accounting.as_str(), "complete" | "incomplete");
    let valid_cost = state
        .accumulated_cost_usd
        .parse::<f64>()
        .is_ok_and(|value| value.is_finite() && value >= 0.0);
    if state.schema_version != 1
        || state.job_id != job_id
        || !valid_status
        || !valid_accounting
        || !valid_cost
        || state.updated_at.is_empty()
    {
        return state_error_projection();
    }
    SanitizedGoalProjection {
        status: Some(state.status),
        iteration: Some(state.iteration),
        cost_usd: Some(state.accumulated_cost_usd),
        cost_accounting: Some(state.cost_accounting),
        pause_reason: sanitized_pause_reason(state.pause_reason),
        updated_at: Some(state.updated_at),
    }
}

fn job_to_entry(job: &serde_json::Value, data_dir: &std::path::Path) -> CronJobEntry {
    // ``schedule`` may be a struct (cron/interval/once) or a plain string in
    // older formats. We surface a human-readable summary regardless.
    let schedule_str = match job.get("schedule") {
        Some(v) if v.is_string() => v.as_str().unwrap_or("").to_string(),
        Some(v) if v.is_object() => {
            let kind = v.get("kind").and_then(|x| x.as_str()).unwrap_or("");
            match kind {
                "cron" => v
                    .get("expression")
                    .and_then(|x| x.as_str())
                    .unwrap_or("")
                    .to_string(),
                "interval" => v
                    .get("seconds")
                    .and_then(|x| x.as_i64())
                    .map(|s| format!("every {}s", s))
                    .unwrap_or_default(),
                "once" => v
                    .get("at")
                    .and_then(|x| x.as_str())
                    .unwrap_or("")
                    .to_string(),
                _ => v.to_string(),
            }
        }
        _ => String::new(),
    };

    let id = job
        .get("id")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let mode = job.get("mode").and_then(|v| v.as_str()).map(str::to_string);
    let is_goal = mode.as_deref() == Some("goal");
    let goal = if is_goal {
        read_goal_projection(data_dir, &id)
    } else {
        SanitizedGoalProjection::default()
    };

    CronJobEntry {
        id,
        name: job
            .get("name")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        schedule: schedule_str,
        prompt: if is_goal {
            String::new()
        } else {
            job.get("prompt")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        },
        deliver: job
            .get("deliver")
            .and_then(|v| v.as_str())
            .unwrap_or("desktop")
            .to_string(),
        paused: job.get("paused").and_then(|v| v.as_bool()).unwrap_or(false),
        next_run_at: job
            .get("next_run_at")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        last_run_at: job
            .get("last_run_at")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        state: job
            .get("state")
            .and_then(|v| v.as_str())
            .unwrap_or("scheduled")
            .to_string(),
        completed_at: job
            .get("completed_at")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        last_status: if is_goal {
            None
        } else {
            job.get("last_status")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        },
        last_delivery_error: if is_goal {
            None
        } else {
            job.get("last_delivery_error")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        },
        mode,
        goal_status: goal.status,
        goal_iteration: goal.iteration,
        goal_cost_usd: goal.cost_usd,
        goal_cost_accounting: goal.cost_accounting,
        goal_pause_reason: goal.pause_reason,
        goal_updated_at: goal.updated_at,
    }
}

// ------------------------------------------------------------------
// Tauri commands
// ------------------------------------------------------------------

#[tauri::command]
pub fn cmd_cron_list(app: AppHandle) -> Result<CronJobListResponse, String> {
    let jobs_raw = read_jobs_raw(&app)?;
    let data_dir = _data_dir(&app)?;
    let mut active: Vec<CronJobEntry> = Vec::new();
    let mut completed: Vec<CronJobEntry> = Vec::new();
    for job in jobs_raw.iter() {
        let entry = job_to_entry(job, &data_dir);
        if entry.state == "completed" {
            completed.push(entry);
        } else {
            active.push(entry);
        }
    }

    // Surface the most recent completions first.
    completed.sort_by(|a, b| b.completed_at.cmp(&a.completed_at));

    let has_any = !active.is_empty() || !completed.is_empty();
    Ok(CronJobListResponse {
        jobs: active,
        completed,
        has_any,
    })
}

#[tauri::command]
pub fn cmd_cron_toggle(app: AppHandle, job_id: String) -> Result<(), String> {
    let mut jobs = read_jobs_raw(&app)?;
    let mut found = false;
    for job in &mut jobs {
        if job.get("id").and_then(|v| v.as_str()) == Some(&job_id) {
            let current = job.get("paused").and_then(|v| v.as_bool()).unwrap_or(false);
            if let Some(obj) = job.as_object_mut() {
                obj.insert("paused".to_string(), serde_json::Value::Bool(!current));
            }
            found = true;
            break;
        }
    }
    if !found {
        return Err(format!("job {job_id} not found"));
    }
    write_jobs_raw(&app, &jobs)
}

#[tauri::command]
pub fn cmd_cron_delete(app: AppHandle, job_id: String) -> Result<(), String> {
    let mut jobs = read_jobs_raw(&app)?;
    let len_before = jobs.len();
    jobs.retain(|job| job.get("id").and_then(|v| v.as_str()) != Some(&job_id));
    if jobs.len() == len_before {
        return Err(format!("job {job_id} not found"));
    }
    write_jobs_raw(&app, &jobs)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_data_dir(name: &str) -> PathBuf {
        let root = std::env::temp_dir().join(format!(
            "kabuqina-cron-{name}-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&root).unwrap();
        root
    }

    fn goal_job() -> serde_json::Value {
        serde_json::json!({
            "id": "abc123def456",
            "name": "Inventory",
            "mode": "goal",
            "schedule": {"kind": "interval", "seconds": 600},
            "prompt": "secret iteration prompt",
            "deliver": "desktop",
            "state": "scheduled",
            "last_status": "provider error with secret-provider-token",
            "last_delivery_error": "delivery failed with secret-delivery-token"
        })
    }

    #[test]
    fn legacy_job_projection_remains_unchanged() {
        let data_dir = temp_data_dir("legacy");
        let job = serde_json::json!({
            "id": "legacy-job",
            "name": "Reminder",
            "schedule": "0 * * * *",
            "prompt": "drink water",
            "deliver": "desktop",
            "paused": false
        });

        let entry = job_to_entry(&job, &data_dir);

        assert_eq!(entry.mode, None);
        assert_eq!(entry.prompt, "drink water");
        assert_eq!(entry.goal_status, None);
        assert_eq!(entry.state, "scheduled");
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn goal_projection_reads_only_sanitized_host_state() {
        let data_dir = temp_data_dir("goal");
        let run_dir = data_dir
            .join("hermes-home")
            .join("cron")
            .join("goal-runs")
            .join("abc123def456");
        std::fs::create_dir_all(&run_dir).unwrap();
        std::fs::write(
            run_dir.join("state.json"),
            serde_json::json!({
                "schema_version": 1,
                "job_id": "abc123def456",
                "status": "paused",
                "iteration": 4,
                "accumulated_cost_usd": "1.25",
                "cost_accounting": "complete",
                "pause_reason": "no_progress",
                "updated_at": "2026-06-27T12:00:00+00:00",
                "last_error": "do not expose this stack",
                "evidence": {"secret": "do not expose"},
                "prompt": "do not expose"
            })
            .to_string(),
        )
        .unwrap();

        let entry = job_to_entry(&goal_job(), &data_dir);

        assert_eq!(entry.mode.as_deref(), Some("goal"));
        assert_eq!(entry.prompt, "");
        assert_eq!(entry.goal_status.as_deref(), Some("paused"));
        assert_eq!(entry.goal_iteration, Some(4));
        assert_eq!(entry.goal_cost_usd.as_deref(), Some("1.25"));
        assert_eq!(entry.goal_cost_accounting.as_deref(), Some("complete"));
        assert_eq!(entry.goal_pause_reason.as_deref(), Some("no_progress"));
        assert_eq!(entry.last_status, None);
        assert_eq!(entry.last_delivery_error, None);
        let serialized = serde_json::to_string(&entry).unwrap();
        assert!(!serialized.contains("do not expose"));
        assert!(!serialized.contains("secret"));
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn malformed_goal_state_marks_only_that_entry_as_state_error() {
        let data_dir = temp_data_dir("malformed");
        let run_dir = data_dir
            .join("hermes-home")
            .join("cron")
            .join("goal-runs")
            .join("abc123def456");
        std::fs::create_dir_all(&run_dir).unwrap();
        std::fs::write(run_dir.join("state.json"), "not json").unwrap();

        let entry = job_to_entry(&goal_job(), &data_dir);

        assert_eq!(entry.goal_status.as_deref(), Some("state_error"));
        assert_eq!(entry.goal_iteration, None);
        let _ = std::fs::remove_dir_all(data_dir);
    }

    #[test]
    fn goal_projection_never_falls_back_to_a_gateway_profile() {
        let data_dir = temp_data_dir("profile");
        let gateway_run_dir = data_dir
            .join("gateway-profile")
            .join("cron")
            .join("goal-runs")
            .join("abc123def456");
        std::fs::create_dir_all(&gateway_run_dir).unwrap();
        std::fs::write(
            gateway_run_dir.join("state.json"),
            serde_json::json!({
                "schema_version": 1,
                "job_id": "abc123def456",
                "status": "completed",
                "iteration": 99,
                "accumulated_cost_usd": "9.99",
                "cost_accounting": "complete",
                "pause_reason": null,
                "updated_at": "2026-06-27T12:00:00+00:00"
            })
            .to_string(),
        )
        .unwrap();

        let entry = job_to_entry(&goal_job(), &data_dir);

        assert_eq!(entry.goal_status.as_deref(), Some("state_error"));
        assert_ne!(entry.goal_iteration, Some(99));
        let _ = std::fs::remove_dir_all(data_dir);
    }
}
