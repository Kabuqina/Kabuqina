# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Auto-download EasyOCR weights (with approval) the first time OCR is used.

EasyOCR is shipped as an on-demand load-package (see ``easyocr_models.py``),
not bundled in the installer. ``tools/ocr_tools.ocr_image_tool`` resolves the
model dir via the module-global ``resolve_easyocr_model_dir()`` at call time, so
wrapping that global lets us trigger the download right before OCR runs —
without editing the frozen upstream ``hermes_core`` tree.

If the weights are already present (downloaded or bundled) the wrapper is a
no-op. If the user declines the download, the original ``ocr_image_tool`` still
emits its clean ``easyocr_models_missing`` error.
"""

from __future__ import annotations

import logging

log = logging.getLogger("hermesdesk.easyocr_autodownload")

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        from tools import ocr_tools  # type: ignore
    except Exception as e:  # pragma: no cover - tools not yet importable
        log.warning("tools.ocr_tools not importable; EasyOCR auto-download not wired (%s)", e)
        return

    original_resolve = ocr_tools.resolve_easyocr_model_dir
    if getattr(original_resolve, "_kabuqina_easyocr_wrapped", False):
        _INSTALLED = True
        return

    def resolve_with_autodownload(*args, **kwargs):
        found = original_resolve(*args, **kwargs)
        if found is not None:
            return found
        # Missing -> try a one-time, approval-gated download, then re-resolve.
        try:
            from easyocr_models import ensure_easyocr_available

            ensure_easyocr_available(
                reason="Kabuqina needs the EasyOCR pack to extract text from this image/scanned page."
            )
        except Exception as exc:  # noqa: BLE001 - fall back to the clean missing error
            log.info("EasyOCR auto-download skipped/failed: %s", exc)
            return None
        return original_resolve(*args, **kwargs)

    resolve_with_autodownload._kabuqina_easyocr_wrapped = True  # type: ignore[attr-defined]
    ocr_tools.resolve_easyocr_model_dir = resolve_with_autodownload  # type: ignore[assignment]
    log.info("EasyOCR auto-download wired into ocr_image")
    _INSTALLED = True
