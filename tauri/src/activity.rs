// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Global Activity command proxying the trusted read-only desk projection.

use crate::chat::DeskBridgeError;
use serde_json::Value;
use std::collections::HashSet;
use tauri::AppHandle;

const ACTIVITY_STATUSES: &[&str] = &[
    "running",
    "waiting",
    "interrupted",
    "failed",
    "completed",
    "recoverable",
];

fn activity_query(statuses: Option<Vec<String>>, limit: u32) -> Result<String, DeskBridgeError> {
    let allowed: HashSet<&str> = ACTIVITY_STATUSES.iter().copied().collect();
    let mut query = url::form_urlencoded::Serializer::new(String::new());
    query.append_pair("limit", &limit.to_string());
    if let Some(statuses) = statuses {
        for status in statuses {
            let status = status.trim();
            if !allowed.contains(status) {
                return Err(DeskBridgeError::invalid(
                    "activity_invalid_request",
                    "activity status is invalid",
                ));
            }
            query.append_pair("statuses", status);
        }
    }
    Ok(query.finish())
}

#[tauri::command]
pub async fn cmd_activity_records(
    app: AppHandle,
    statuses: Option<Vec<String>>,
    limit: Option<u32>,
) -> Result<Value, DeskBridgeError> {
    let limit = limit.unwrap_or(100);
    if !(1..=100).contains(&limit) {
        return Err(DeskBridgeError::invalid(
            "activity_invalid_request",
            "limit must be within 1..100",
        ));
    }
    let query = activity_query(statuses, limit)?;
    let path = format!("/api/desk/activity?{query}");
    crate::chat::desk_json_request_structured(&app, reqwest::Method::GET, &path, None).await
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn public_activity_statuses_are_stable() {
        assert!(ACTIVITY_STATUSES.contains(&"recoverable"));
        assert!(!ACTIVITY_STATUSES.contains(&"waiting_for_learner"));
    }
}
