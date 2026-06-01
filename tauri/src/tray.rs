// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

//! System tray icon + minimal menu.

use anyhow::Result;
use tauri::{
    image::Image,
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, TrayIconBuilder, TrayIconEvent},
    App, Manager, WindowEvent,
};

/// Closing the main window hides to tray instead of destroying the webview.
pub fn install_main_close_hides_to_tray(app: &App) -> Result<()> {
    let Some(main) = app.get_webview_window("main") else {
        return Ok(());
    };
    let main_for_event = main.clone();
    main.on_window_event(move |event| {
        if let WindowEvent::CloseRequested { api, .. } = event {
            api.prevent_close();
            let _ = main_for_event.hide();
        }
    });
    Ok(())
}

pub fn install(app: &mut App) -> Result<()> {
    let handle = app.handle().clone();

    let show = MenuItem::with_id(&handle, "show", "Open Kabuqina", true, None::<&str>)?;
    let workspace = MenuItem::with_id(
        &handle,
        "workspace",
        "Open workspace folder",
        true,
        None::<&str>,
    )?;
    let companion = MenuItem::with_id(
        &handle,
        "companion",
        "Show Nana pill",
        true,
        None::<&str>,
    )?;
    let updates = MenuItem::with_id(&handle, "updates", "Check for updates", true, None::<&str>)?;
    let sep = PredefinedMenuItem::separator(&handle)?;
    let quit = MenuItem::with_id(&handle, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(
        &handle,
        &[&show, &companion, &workspace, &updates, &sep, &quit],
    )?;

    let icon = Image::from_bytes(include_bytes!("../icons/tray.png"))?;

    let _ = TrayIconBuilder::with_id("kabuqina-tray")
        .icon(icon)
        .tooltip("卡布奇娜")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id().as_ref() {
            "show" => {
                crate::companion::focus_main_window(&app);
            }
            "workspace" => {
                let _ = crate::paths::cmd_open_workspace(app.clone());
            }
            "companion" => {
                tauri::async_runtime::spawn({
                    let app = app.clone();
                    async move {
                        if let Err(e) = crate::companion::show_companion(app).await {
                            log::error!("show companion: {e}");
                        }
                    }
                });
            }
            "updates" => {
                #[cfg(desktop)]
                tauri::async_runtime::spawn({
                    let app = app.clone();
                    async move {
                        use tauri_plugin_updater::UpdaterExt;
                        if let Ok(updater) = app.updater() {
                            let _ = updater.check().await;
                        }
                    }
                });
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                ..
            } = event
            {
                let app = tray.app_handle();
                crate::companion::focus_main_window(app);
            }
        })
        .build(app)?;

    Ok(())
}
