// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

// Prevents additional console window on Windows in release.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    kabuqina_lib::run()
}
