# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0

"""Disable unused bundled image_gen backend plugins for the desktop build.

Upstream Hermes auto-loads ``kind: backend`` bundled plugins during
``discover_plugins()`` — including the OpenAI / OpenAI-Codex / xAI image
generation providers. Kabuqina does not surface an image_gen provider
picker, and these backends are never selected, so registering them only
adds startup log noise (``Plugin '<name>' registered image_gen provider``)
for code paths that can never run.

Rather than delete the upstream plugin directories (which would conflict on
every hermes_core sync), this overlay seeds the framework's own
``plugins.disabled`` deny-list with their path-derived keys. Discovery then
skips them (see ``PluginManager.discover_plugins`` →
``_get_disabled_plugins``), so they never register and never log.

The seed is additive and idempotent: it only appends keys that aren't
already disabled and never removes a user's own entries. The provider
*mechanism* (registry + ``image_gen.provider`` dispatch) is untouched, so a
different backend can still be wired up later.
"""

from __future__ import annotations

import logging

log = logging.getLogger("hermesdesk.disable_image_gen_backends")

_INSTALLED = False

# Path-derived registry keys for the bundled image_gen backends we never use.
# ``_get_disabled_plugins`` matches on the plugin's lookup key (the
# ``plugins/<category>/<name>`` path form for nested plugins), so the keys
# below correspond to ``plugins/image_gen/{openai,openai-codex,xai}``.
_DISABLED_IMAGE_GEN_BACKENDS = (
    "image_gen/openai",
    "image_gen/openai-codex",
    "image_gen/xai",
)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    try:
        from hermes_cli.config import load_config, save_config  # type: ignore
    except Exception as e:  # pragma: no cover - import wiring guard
        log.warning("hermes_cli.config not importable; skipping image_gen disable (%s)", e)
        return

    try:
        cfg = load_config() or {}
    except Exception as e:
        log.warning("could not load config for image_gen disable (%s)", e)
        return

    plugins = cfg.get("plugins")
    if not isinstance(plugins, dict):
        plugins = {}
    disabled = plugins.get("disabled")
    if not isinstance(disabled, list):
        disabled = []

    missing = [key for key in _DISABLED_IMAGE_GEN_BACKENDS if key not in disabled]
    if not missing:
        _INSTALLED = True
        return

    plugins["disabled"] = disabled + missing
    cfg["plugins"] = plugins

    try:
        save_config(cfg)
        log.info(
            "image_gen backends disabled by default: %s",
            ", ".join(missing),
        )
    except Exception:
        log.exception("failed to save image_gen disable seed")
        return

    _INSTALLED = True
