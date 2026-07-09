# Copyright 2026 Kabuqina Contributors
# SPDX-License-Identifier: Apache-2.0
"""Drift guard for the two provider-description structures (phase 3b).

`HERMES_OVERLAYS` (`hermes_cli.providers`) and `PROVIDER_REGISTRY`
(`hermes_cli.auth`) are intentionally separate — they serve two subsystems:

* `PROVIDER_REGISTRY` is the auth + **live runtime** source of truth
  (`runtime_provider.resolve_runtime_provider`, login flows, credential pool).
  ``model_switch`` already calls it "our source of truth" for env-var names.
* `HERMES_OVERLAYS` is the identity/routing overlay on the models.dev catalog —
  it only needs to add `transport` / `is_aggregator` that models.dev lacks.

Phase 3b investigation (2026-06-24) concluded they should NOT be merged into one
structure: a merge would reconcile two different id schemes and re-route the live
request path, a hot-path change disproportionate to de-duping ~18 small entries.
Instead this test pins the relationship so the fields they *do* share can't
silently drift — the actual maintenance hazard of a double layer.

If you add a provider, add it to whichever structure(s) it belongs to and update
the explicit asymmetry sets below if the new provider is intentionally one-sided.
"""

from __future__ import annotations

import pytest

from hermes_cli.auth import PROVIDER_REGISTRY
from hermes_cli.providers import HERMES_OVERLAYS

# Overlay ids that use a models.dev slug differing from the registry's auth id.
_OVERLAY_TO_REGISTRY_ID = {"kimi-for-coding": "kimi-coding"}

# Intentional one-sided membership (documented, not drift):
#  - openrouter: an aggregator with no dedicated login flow → overlay only.
#  - gemini / kimi-coding-cn: have auth/runtime config but no models.dev overlay.
#  - spark: 讯飞星火 (China) has auth/runtime config but no models.dev overlay.
_OVERLAY_ONLY = {"openrouter"}
_REGISTRY_ONLY = {"gemini", "kimi-coding-cn", "spark"}

# Providers whose overlay/registry auth_type intentionally differs. Empty: the
# former minimax-oauth divergence (overlay "oauth_external" vs registry
# "oauth_minimax") was reconciled — the overlay now matches the registry's
# login-driving value.
_AUTH_TYPE_DIVERGENCE: set[str] = set()


def _registry_for(overlay_id: str):
    return PROVIDER_REGISTRY.get(_OVERLAY_TO_REGISTRY_ID.get(overlay_id, overlay_id))


def _aligned_overlay_ids():
    return [oid for oid in HERMES_OVERLAYS if _registry_for(oid) is not None]


def test_membership_asymmetry_is_as_declared():
    """A provider added to only one structure must be intentional (in the sets)."""
    aligned_registry_ids = {
        _OVERLAY_TO_REGISTRY_ID.get(oid, oid) for oid in _aligned_overlay_ids()
    }
    overlay_only = {oid for oid in HERMES_OVERLAYS if _registry_for(oid) is None}
    registry_only = {rid for rid in PROVIDER_REGISTRY if rid not in aligned_registry_ids}

    assert overlay_only == _OVERLAY_ONLY, (
        f"overlay-only providers changed: {overlay_only} (expected {_OVERLAY_ONLY}). "
        "Add the provider to PROVIDER_REGISTRY too, or update _OVERLAY_ONLY."
    )
    assert registry_only == _REGISTRY_ONLY, (
        f"registry-only providers changed: {registry_only} (expected {_REGISTRY_ONLY}). "
        "Add the provider to HERMES_OVERLAYS too, or update _REGISTRY_ONLY."
    )


@pytest.mark.parametrize("overlay_id", sorted(_aligned_overlay_ids()))
def test_shared_fields_do_not_drift(overlay_id):
    overlay = HERMES_OVERLAYS[overlay_id]
    reg = _registry_for(overlay_id)

    # base_url override env var: where the overlay sets it, it must match.
    if overlay.base_url_env_var:
        assert overlay.base_url_env_var == reg.base_url_env_var, (
            f"{overlay_id}: base_url_env_var drift "
            f"(overlay {overlay.base_url_env_var!r} vs registry {reg.base_url_env_var!r})"
        )

    # The overlay's extra env vars must be a subset of the registry's full set
    # (the registry is the source of truth for api-key env var names).
    missing = set(overlay.extra_env_vars) - set(reg.api_key_env_vars)
    assert not missing, (
        f"{overlay_id}: overlay extra_env_vars {missing} not in registry "
        f"api_key_env_vars {reg.api_key_env_vars}"
    )

    # auth_type must agree, except the tracked minimax-oauth divergence.
    if overlay_id not in _AUTH_TYPE_DIVERGENCE:
        assert overlay.auth_type == reg.auth_type, (
            f"{overlay_id}: auth_type drift "
            f"(overlay {overlay.auth_type!r} vs registry {reg.auth_type!r})"
        )
