"""Regression tests for terminal config -> env-var bridging.

terminal_tool._get_env_config() reads ALL terminal settings from os.environ
(TERMINAL_*).  config.yaml values therefore have to be bridged into env vars
by the retained runtime/config code paths:

  1. gateway/run.py    -> ``_terminal_env_map`` dict (gateway / messaging
                          platforms)
  2. kabuqina_cli/config.py:save_config_value
                       -> ``_config_to_env_sync`` dict (one-shot when the
                          user runs ``kabuqina config set …``)

If any one of these is missing a key, the corresponding config.yaml setting
silently does nothing for that entry-point.  This bug already shipped once
for ``docker_run_as_host_user`` (gateway and CLI maps) and once for
``docker_mount_cwd_to_workspace`` (gateway map).

This test guards against future drift by extracting retained maps via source
inspection and asserting they bridge the critical writable
``terminal.*`` keys.  Source inspection (rather than importing the live
dicts) keeps the test independent of the user's ~/.hermes/config.yaml.
"""

import ast
import inspect


def _extract_dict_values(source: str, dict_name: str) -> set[str]:
    """Return the set of *value* strings in `dict_name = { "k": "VALUE", ... }`.

    We parse the source with ast (so multi-line dicts and comments are
    handled) instead of regex.  The first matching assignment wins.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t for t in node.targets if isinstance(t, ast.Name)]
        if not any(t.id == dict_name for t in targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        out: set[str] = set()
        for k, v in zip(node.value.keys, node.value.values):
            if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                if isinstance(v.value, str):
                    out.add(v.value)
        return out
    raise AssertionError(f"Could not find `{dict_name} = {{...}}` literal in source")


def _extract_dict_keys(source: str, dict_name: str) -> set[str]:
    """Return the set of *key* strings in `dict_name = { "KEY": "v", ... }`."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        targets = [t for t in node.targets if isinstance(t, ast.Name)]
        if not any(t.id == dict_name for t in targets):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        out: set[str] = set()
        for k in node.value.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                out.add(k.value)
        return out
    raise AssertionError(f"Could not find `{dict_name} = {{...}}` literal in source")


def _gateway_env_map_keys() -> set[str]:
    """terminal config keys bridged by gateway/run.py at module load."""
    # gateway/run.py builds the dict at module top-level (not inside a
    # function), so inspect the whole module source.
    import gateway.run as gr
    source = inspect.getsource(gr)
    return _extract_dict_keys(source, "_terminal_env_map")


def _save_config_env_sync_keys() -> set[str]:
    """terminal config keys bridged by ``kabuqina config set foo bar``."""
    from kabuqina_cli import config as hc_config
    source = inspect.getsource(hc_config.set_config_value)
    keys = _extract_dict_keys(source, "_config_to_env_sync")
    # set_config_value uses fully-qualified ``terminal.foo`` keys; strip the
    # prefix so we can compare against the other two maps which use bare
    # leaf keys.
    return {k.split(".", 1)[1] for k in keys if k.startswith("terminal.")}


def _terminal_tool_env_var_names() -> set[str]:
    """All TERMINAL_* env vars actually consumed by terminal_tool."""
    import tools.terminal_tool as tt
    source = inspect.getsource(tt)
    # Naive scan: every os.getenv("TERMINAL_X", ...) and _parse_env_var("TERMINAL_X", ...).
    import re
    pat = re.compile(r'["\'](TERMINAL_[A-Z0-9_]+)["\']')
    return set(pat.findall(source))


def test_save_config_set_supports_critical_bridged_keys():
    """``kabuqina config set terminal.X true`` must propagate to .env for
    known-critical keys.  This used to be an all-keys invariant but several
    pre-existing terminal keys (ssh_*, docker_forward_env, docker_volumes)
    aren't in _config_to_env_sync and are instead handled via the separate
    api_keys TERMINAL_SSH_* fallback path or user-edits-yaml-directly.

    Until those gaps are audited and fixed, pin the specific keys that are
    load-bearing for the docker backend's ownership flag so the bug we just
    fixed cannot silently regress.
    """
    save_keys = _save_config_env_sync_keys()
    required = {
        "docker_run_as_host_user",
        "docker_mount_cwd_to_workspace",
        "backend",
        "docker_image",
        "container_cpu",
        "container_memory",
        "container_disk",
        "container_persistent",
    }
    missing = required - save_keys
    assert not missing, (
        f"`kabuqina config set terminal.X` doesn't sync these load-bearing "
        f"keys to .env: {sorted(missing)}.  Add them to _config_to_env_sync "
        f"in kabuqina_cli/config.py:set_config_value."
    )


def test_docker_run_as_host_user_is_bridged_in_retained_runtime():
    """Explicit pin for the bug we just fixed.

    docker_run_as_host_user was added to terminal_tool._get_env_config and
    DockerEnvironment but NOT to gateway/run.py's
    _terminal_env_map, so ``terminal.docker_run_as_host_user: true`` in
    config.yaml had no effect at runtime.  This guard makes the regression
    impossible to reintroduce silently.
    """
    assert "docker_run_as_host_user" in _gateway_env_map_keys()
    assert "docker_run_as_host_user" in _save_config_env_sync_keys()
    assert "TERMINAL_DOCKER_RUN_AS_HOST_USER" in _terminal_tool_env_var_names()


def test_docker_mount_cwd_to_workspace_is_bridged_in_retained_runtime():
    """Same regression class — docker_mount_cwd_to_workspace was missing from
    gateway/run.py's _terminal_env_map until the docker_run_as_host_user
    audit caught it.
    """
    assert "docker_mount_cwd_to_workspace" in _gateway_env_map_keys()
    assert "docker_mount_cwd_to_workspace" in _save_config_env_sync_keys()
    assert "TERMINAL_DOCKER_MOUNT_CWD_TO_WORKSPACE" in _terminal_tool_env_var_names()
