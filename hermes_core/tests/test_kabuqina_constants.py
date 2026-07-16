"""Tests for canonical Kabuqina home and constants."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import kabuqina_constants
import hermes_constants
from kabuqina_constants import get_default_kabuqina_root, get_kabuqina_home, is_container


class TestGetKabuqinaHome:
    def test_new_env_wins_over_legacy_env(self, tmp_path, monkeypatch):
        current = tmp_path / "current"
        legacy = tmp_path / "legacy"
        monkeypatch.setenv("KABUQINA_HOME", str(current))
        monkeypatch.setenv("HERMES_HOME", str(legacy))
        assert get_kabuqina_home() == current

    def test_explicit_empty_new_env_suppresses_legacy_env(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("KABUQINA_HOME", "")
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "legacy"))
        assert get_kabuqina_home() == tmp_path / ".kabuqina"

    def test_legacy_module_exports_old_function_names(self, tmp_path, monkeypatch):
        """Deprecated names preserve behavior across canonical module reloads.

        Broad-suite tests intentionally reload ``kabuqina_constants``. A
        reload recreates function objects, so object identity is not part of
        the compatibility contract; importability and equivalent resolution
        behavior are.
        """
        current = tmp_path / "current"
        monkeypatch.setenv("KABUQINA_HOME", str(current))
        monkeypatch.setenv("HERMES_HOME", str(tmp_path / "legacy"))

        assert callable(hermes_constants.get_hermes_home)
        assert callable(hermes_constants.get_default_hermes_root)
        assert callable(hermes_constants.get_hermes_dir)
        assert callable(hermes_constants.display_hermes_home)
        assert (
            hermes_constants.get_hermes_home()
            == kabuqina_constants.get_kabuqina_home()
            == current
        )
        assert (
            hermes_constants.get_default_hermes_root()
            == kabuqina_constants.get_default_kabuqina_root()
        )
        assert hermes_constants.get_hermes_dir("cache/images", "image_cache") == (
            kabuqina_constants.get_kabuqina_dir("cache/images", "image_cache")
        )
        assert (
            hermes_constants.display_hermes_home()
            == kabuqina_constants.display_kabuqina_home()
        )

    def test_legacy_env_fallback(self, tmp_path, monkeypatch):
        legacy = tmp_path / "legacy"
        monkeypatch.delenv("KABUQINA_HOME", raising=False)
        monkeypatch.setenv("HERMES_HOME", str(legacy))
        assert get_kabuqina_home() == legacy

    def test_existing_legacy_default_is_read_for_one_release(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("KABUQINA_HOME", raising=False)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        legacy = tmp_path / ".hermes"
        legacy.mkdir()
        assert get_kabuqina_home() == legacy

    def test_new_default_wins_when_both_default_dirs_exist(self, tmp_path, monkeypatch):
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.delenv("KABUQINA_HOME", raising=False)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        (tmp_path / ".hermes").mkdir()
        (tmp_path / ".kabuqina").mkdir()
        assert get_kabuqina_home() == tmp_path / ".kabuqina"


class TestGetDefaultKabuqinaRoot:
    """Tests for profile and custom deployment awareness."""

    def test_no_kabuqina_home_returns_native(self, tmp_path, monkeypatch):
        """When neither home env is set, returns ~/.kabuqina."""
        monkeypatch.delenv("KABUQINA_HOME", raising=False)
        monkeypatch.delenv("HERMES_HOME", raising=False)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert get_default_kabuqina_root() == tmp_path / ".kabuqina"

    def test_kabuqina_home_is_native(self, tmp_path, monkeypatch):
        """When KABUQINA_HOME = ~/.kabuqina, returns ~/.kabuqina."""
        native = tmp_path / ".kabuqina"
        native.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("KABUQINA_HOME", str(native))
        assert get_default_kabuqina_root() == native

    def test_kabuqina_home_is_profile(self, tmp_path, monkeypatch):
        """When KABUQINA_HOME is a profile under ~/.kabuqina, returns its root."""
        native = tmp_path / ".kabuqina"
        profile = native / "profiles" / "coder"
        profile.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("KABUQINA_HOME", str(profile))
        assert get_default_kabuqina_root() == native

    def test_kabuqina_home_is_docker(self, tmp_path, monkeypatch):
        """When KABUQINA_HOME points outside ~/.kabuqina, return it."""
        docker_home = tmp_path / "opt" / "data"
        docker_home.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("KABUQINA_HOME", str(docker_home))
        assert get_default_kabuqina_root() == docker_home

    def test_kabuqina_home_is_custom_path(self, tmp_path, monkeypatch):
        """Any KABUQINA_HOME outside ~/.kabuqina is treated as the root."""
        custom = tmp_path / "my-kabuqina-data"
        custom.mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("KABUQINA_HOME", str(custom))
        assert get_default_kabuqina_root() == custom

    def test_docker_profile_active(self, tmp_path, monkeypatch):
        """When a Docker profile is active (KABUQINA_HOME=<root>/profiles/<name>),
        returns the Docker root, not the profile dir."""
        docker_root = tmp_path / "opt" / "data"
        profile = docker_root / "profiles" / "coder"
        profile.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setenv("KABUQINA_HOME", str(profile))
        assert get_default_kabuqina_root() == docker_root


class TestIsContainer:
    """Tests for is_container() — Docker/Podman detection."""

    def _reset_cache(self, monkeypatch):
        """Reset the cached detection result before each test."""
        monkeypatch.setattr(kabuqina_constants, "_container_detected", None)

    def test_detects_dockerenv(self, monkeypatch, tmp_path):
        """/.dockerenv triggers container detection."""
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: p == "/.dockerenv")
        assert is_container() is True

    def test_detects_containerenv(self, monkeypatch, tmp_path):
        """/run/.containerenv triggers container detection (Podman)."""
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: p == "/run/.containerenv")
        assert is_container() is True

    def test_detects_cgroup_docker(self, monkeypatch, tmp_path):
        """/proc/1/cgroup containing 'docker' triggers detection."""
        import builtins
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text("12:memory:/docker/abc123\n")
        _real_open = builtins.open
        monkeypatch.setattr("builtins.open", lambda p, *a, **kw: _real_open(str(cgroup_file), *a, **kw) if p == "/proc/1/cgroup" else _real_open(p, *a, **kw))
        assert is_container() is True

    def test_negative_case(self, monkeypatch, tmp_path):
        """Returns False on a regular Linux host."""
        import builtins
        self._reset_cache(monkeypatch)
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        cgroup_file = tmp_path / "cgroup"
        cgroup_file.write_text("12:memory:/\n")
        _real_open = builtins.open
        monkeypatch.setattr("builtins.open", lambda p, *a, **kw: _real_open(str(cgroup_file), *a, **kw) if p == "/proc/1/cgroup" else _real_open(p, *a, **kw))
        assert is_container() is False

    def test_caches_result(self, monkeypatch):
        """Second call uses cached value without re-probing."""
        monkeypatch.setattr(kabuqina_constants, "_container_detected", True)
        assert is_container() is True
        # Even if we make os.path.exists return False, cached value wins
        monkeypatch.setattr(os.path, "exists", lambda p: False)
        assert is_container() is True
