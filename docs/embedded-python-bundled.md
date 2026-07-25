# Embedded Python bundle (Windows)

Kabuqina ships a **standalone CPython** plus pruned **`site-packages`**, the canonical **`kabuqina/`** core subtree, **`overlays/`**, and launcher scripts under **`python/dist/runtime/`**. Tauri copies this tree into the build output (`tauri/target/.../runtime`) for dev and release.

## How to build

From repo root:

```powershell
.\python\build_bundle.ps1
```

Options (`-Clean`, `-Verify`, `-SkipWebBuild`) are documented in the script header — see [`python/build_bundle.ps1`](../python/build_bundle.ps1).

After **`git pull`** or changes under **`hermes_core/`**, especially `gateway/`, **re-run** `build_bundle.ps1` before expecting bundled messaging fixes to appear ([`troubleshooting.md`](troubleshooting.md) §12).

## Shared download cache

Fixed CPython/STT archives and the lock-resolved WhatsApp bridge dependencies
are cached under `%LOCALAPPDATA%\Kabuqina\bundle-cache`. The cache is shared by
all Git worktrees, so changing worktrees does not download the same fixed files
again. Set `KABUQINA_BUNDLE_CACHE` to an absolute directory to override it.
An existing worktree-local `python/_download/` is copied into the shared cache
once without deleting the old files.

WhatsApp dependencies are installed during the build from the committed
`package-lock.json` and cached by its SHA-256. The desktop runtime never runs
`npm install`.

## Dependency evidence

Every completed runtime contains `DEPENDENCY_INVENTORY.json`, which records the
exact installed Python and Node package versions, published license metadata,
and the hashes of the desktop requirements and WhatsApp lock. The success
marker `BUNDLE_INFO.json` also records hashes for that inventory,
`requirements-desktop.txt`, the WhatsApp lock, and the tracked
`tauri/Cargo.lock`. A `-Verify` build fails if retained Python distributions or
the direct WhatsApp bridge payload are absent.

## MSVC / wheels

Release and some dev builds compile or pull wheels (e.g. **`pydantic-core`**) that expect a **Visual C++** toolchain. Prefer **Developer PowerShell for VS** or **cmd.exe** with MSVC environment when the bundler fails on native extensions; see repo **`README.md`** build section.

## Related

- [`architecture.md`](architecture.md) — `desktop_entrypoint.py` vs `python -m gateway.run`
- [`Kabuqina-capability-matrix.md`](Kabuqina-capability-matrix.md)
