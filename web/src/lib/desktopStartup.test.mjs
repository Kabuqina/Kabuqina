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
  mainSource.includes("showMainWindowWhenReady"),
  "The main webview should call showMainWindowWhenReady() after React has rendered the first frame.",
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
  libSource.includes("cmd_get_hermes_desk_boot_state"),
  "Shell boot UI should read desk warm state via cmd_get_hermes_desk_boot_state.",
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
