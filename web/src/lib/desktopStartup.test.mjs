/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const libSource = fs.readFileSync(new URL("../../../tauri/src/lib.rs", import.meta.url), "utf8");

const bootstrapStart = libSource.indexOf("async fn bootstrap(");
assert.ok(bootstrapStart >= 0, "Tauri bootstrap() should exist.");

const pythonBootstrapStart = libSource.indexOf("let hermes_ok = async", bootstrapStart);
assert.ok(pythonBootstrapStart >= 0, "bootstrap() should start embedded Hermes through hermes_ok.");

const bridgeStartup = libSource.indexOf("bridge::spawn", bootstrapStart);
assert.ok(bridgeStartup >= 0, "bootstrap() should start the loopback bridge.");

const revealMain = libSource.indexOf("reveal_main();", bootstrapStart);
assert.ok(revealMain >= 0, "bootstrap() should reveal the main window.");
assert.ok(
  [...libSource.matchAll(/\breveal_main\(\);/g)].length === 1,
  "Rust should only reveal the main window as a bootstrap-failure fallback; the frontend shows it after first render to avoid a blank webview.",
);

const mainSource = fs.readFileSync(new URL("../main.tsx", import.meta.url), "utf8");
assert.ok(
  mainSource.includes("revealMainWindowAfterShellPaint"),
  "The main webview should reveal only after the shell has mounted and painted.",
);
assert.match(
  mainSource,
  /function MainWindowShell[\s\S]*useEffect[\s\S]*revealMainWindowAfterShellPaint/,
  "The main shell component should own the reveal timing so the native window is not shown before React content exists.",
);
assert.ok(
  mainSource.includes("MAIN_WINDOW_REVEAL_DELAY_MS"),
  "Main window reveal should include a small post-paint delay to avoid a blank WebView first frame.",
);
assert.ok(
  !mainSource.includes("showMainWindowWhenReady();"),
  "The entrypoint should not reveal the main window immediately after ReactDOM.render().",
);

assert.ok(
  libSource.includes("async_runtime::spawn(async move"),
  "Edge CDP should start in a background task so Python spawn is not blocked.",
);

assert.ok(
  libSource.includes("bootstrap bridge_ms="),
  "bootstrap() should log bridge timing for startup diagnostics.",
);

assert.ok(
  libSource.includes("bootstrap port_wait_ms=") || libSource.includes("bootstrap python_spawn_ms="),
  "bootstrap() should log Python spawn / port wait timing.",
);

assert.ok(
  !libSource.includes("cmd_open_hermes_dashboard"),
  "Hermes dashboard browser opener should be removed from the Tauri command list.",
);

assert.ok(
  libSource.includes("cmd_get_kabuqina_boot_state"),
  "Shell boot UI should read desk warm state via cmd_get_kabuqina_boot_state.",
);

const pythonSupervisor = fs.readFileSync(
  new URL("../../../tauri/src/python_supervisor.rs", import.meta.url),
  "utf8",
);
assert.ok(
  pythonSupervisor.includes("HERMESDESK_DESK_MINIMAL"),
  "Python spawn should enable desk-minimal mode.",
);

const entrySource = fs.readFileSync(
  new URL("../../../python/src/desktop_entrypoint.py", import.meta.url),
  "utf8",
);
assert.ok(
  entrySource.includes("boot timing"),
  "desktop_entrypoint should log segmented boot timings.",
);

const buildBundle = fs.readFileSync(
  new URL("../../../python/build_bundle.ps1", import.meta.url),
  "utf8",
);
assert.ok(
  buildBundle.includes("upstream Hermes dashboard SPA is no longer bundled"),
  "build_bundle.ps1 should keep the upstream Hermes dashboard out of the desktop bundle.",
);

const edgeBrowser = fs.readFileSync(
  new URL("../../../tauri/src/edge_browser.rs", import.meta.url),
  "utf8",
);
assert.ok(
  edgeBrowser.includes("--headless=new"),
  "Edge CDP backend should use the modern headless mode so NSIS launches do not expose a blank browser window.",
);
assert.ok(
  edgeBrowser.includes("--disable-gpu"),
  "Headless Edge should disable GPU compositing to avoid visible blank surfaces on Windows.",
);
assert.ok(
  edgeBrowser.includes("--no-startup-window"),
  "Edge CDP backend should explicitly avoid creating an initial blank browser window.",
);

const secretsSource = fs.readFileSync(
  new URL("../../../tauri/src/secrets.rs", import.meta.url),
  "utf8",
);
for (const commandName of ["cmd_save_secret", "cmd_update_llm_config", "cmd_clear_secret"]) {
  const start = secretsSource.indexOf(`pub async fn ${commandName}`);
  assert.ok(start >= 0, `${commandName} should exist.`);
  const nextCommand = secretsSource.indexOf("#[tauri::command]", start + 1);
  const body = secretsSource.slice(start, nextCommand >= 0 ? nextCommand : undefined);
  assert.ok(
    body.includes("schedule_embedded_hermes_respawn(app);"),
    `${commandName} should schedule Python restart in the background after saving credentials.`,
  );
  assert.ok(
    !body.includes("respawn_embedded_hermes_python(app).await?"),
    `${commandName} should not block onboarding while waiting for embedded Python to finish cold-starting.`,
  );
}
