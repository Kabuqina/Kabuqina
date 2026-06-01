// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! Windows toast identity for cron / desktop delivery.
//!
//! `tauri-plugin-notification` skips `app_id` when the exe lives under
//! `target/debug` or `target/release`, so Action Center shows "PowerShell".
//! We always register `com.kabuqina.app` (same as MSI shortcut + bundle id).

#[cfg(windows)]
const AUMID: &str = "com.kabuqina.app";

/// Register the process AUMID once at startup (best-effort).
#[cfg(windows)]
pub fn init() {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::UI::Shell::SetCurrentProcessExplicitAppUserModelID;

    let wide: Vec<u16> = OsStr::new(AUMID).encode_wide().chain(Some(0)).collect();
    unsafe {
        let hr = SetCurrentProcessExplicitAppUserModelID(wide.as_ptr());
        if hr < 0 {
            log::warn!(
                "windows notification: SetCurrentProcessExplicitAppUserModelID failed (HRESULT={hr})"
            );
        }
    }
}

#[cfg(not(windows))]
pub fn init() {}

/// Show a native toast with the Kabuqina app id (non-blocking).
#[cfg(windows)]
pub fn show_toast(title: &str, body: &str) {
    let title = title.to_string();
    let body = body.to_string();
    std::thread::spawn(move || {
        let mut notification = notify_rust::Notification::new();
        notification.summary(&title);
        notification.body(&body);
        notification.app_id(AUMID);
        notification.auto_icon();
        if let Err(e) = notification.show() {
            log::warn!("windows notification: toast failed: {e}");
        }
    });
}

#[cfg(not(windows))]
pub fn show_toast(_title: &str, _body: &str) {}
