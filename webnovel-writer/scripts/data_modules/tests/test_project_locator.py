#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib
import sys
from pathlib import Path

import pytest


def _ensure_scripts_on_path() -> None:
    scripts_dir = Path(__file__).resolve().parents[2]
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))


@pytest.fixture(autouse=True)
def isolate_project_locator_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("WEBNOVEL_PROJECT_ROOT", raising=False)
    monkeypatch.delenv("WEBNOVEL_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("CODEX_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("WEBNOVEL_HOME", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_HOME", raising=False)
    monkeypatch.setenv("WEBNOVEL_CLAUDE_HOME", str(tmp_path / "empty-claude-home"))


def _make_project(root: Path) -> Path:
    (root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")
    return root


def test_resolve_project_root_prefers_cwd_project(tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    project_root = tmp_path / "workspace"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    resolved = resolve_project_root(cwd=project_root)
    assert resolved == project_root.resolve()


def test_resolve_project_root_stops_at_git_root(tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    nested = repo_root / "sub" / "dir"
    nested.mkdir(parents=True, exist_ok=True)

    outside_project = tmp_path / "outside_project"
    (outside_project / ".webnovel").mkdir(parents=True, exist_ok=True)
    (outside_project / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    try:
        resolve_project_root(cwd=nested)
        assert False, "Expected FileNotFoundError when only parent outside git root has project"
    except FileNotFoundError:
        pass


def test_resolve_project_root_finds_default_subdir_within_git_root(tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    repo_root = tmp_path / "repo"
    (repo_root / ".git").mkdir(parents=True, exist_ok=True)

    default_project = repo_root / "webnovel-project"
    (default_project / ".webnovel").mkdir(parents=True, exist_ok=True)
    (default_project / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    nested = repo_root / "sub" / "dir"
    nested.mkdir(parents=True, exist_ok=True)

    resolved = resolve_project_root(cwd=nested)
    assert resolved == default_project.resolve()


def test_resolve_project_root_uses_workspace_pointer(tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root, write_current_project_pointer

    workspace = tmp_path / "workspace"
    (workspace / ".claude").mkdir(parents=True, exist_ok=True)

    project_root = workspace / "凡人资本论"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    pointer_file = write_current_project_pointer(project_root, workspace_root=workspace)
    assert pointer_file is not None
    assert pointer_file.is_file()

    resolved = resolve_project_root(cwd=workspace)
    assert resolved == project_root.resolve()


def test_resolve_project_root_explicit_workspace_uses_unique_child_project(tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    workspace = tmp_path / "workspace"
    (workspace / ".git").mkdir(parents=True, exist_ok=True)
    project_root = workspace / "凡人资本论"
    (project_root / ".webnovel").mkdir(parents=True, exist_ok=True)
    (project_root / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    resolved = resolve_project_root(str(workspace))
    assert resolved == project_root.resolve()


def test_resolve_project_root_ignores_stale_pointer_and_fallbacks(tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    workspace = tmp_path / "workspace"
    (workspace / ".git").mkdir(parents=True, exist_ok=True)
    (workspace / ".claude").mkdir(parents=True, exist_ok=True)
    # stale pointer
    (workspace / ".claude" / ".webnovel-current-project").write_text(
        str(workspace / "missing-project"), encoding="utf-8"
    )

    default_project = workspace / "webnovel-project"
    (default_project / ".webnovel").mkdir(parents=True, exist_ok=True)
    (default_project / ".webnovel" / "state.json").write_text("{}", encoding="utf-8")

    resolved = resolve_project_root(cwd=workspace)
    assert resolved == default_project.resolve()


def test_resolve_project_root_uses_codex_workspace_root_env(monkeypatch, tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    workspace = tmp_path / "workspace"
    (workspace / ".git").mkdir(parents=True, exist_ok=True)
    project_root = _make_project(workspace / "凡人资本论")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("CODEX_WORKSPACE_ROOT", str(workspace))

    resolved = resolve_project_root(cwd=elsewhere)
    assert resolved == project_root.resolve()


def test_resolve_project_root_webnovel_workspace_precedes_codex_root_env(monkeypatch, tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    codex_workspace = tmp_path / "codex-workspace"
    webnovel_workspace = tmp_path / "webnovel-workspace"
    codex_project = _make_project(codex_workspace / "Codex书")
    webnovel_project = _make_project(webnovel_workspace / "Webnovel书")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("CODEX_WORKSPACE_ROOT", str(codex_workspace))
    monkeypatch.setenv("WEBNOVEL_WORKSPACE_ROOT", str(webnovel_workspace))

    resolved = resolve_project_root(cwd=elsewhere)
    assert resolved == webnovel_project.resolve()
    assert resolved != codex_project.resolve()


def test_resolve_project_root_uses_claude_project_dir_env(monkeypatch, tmp_path):
    _ensure_scripts_on_path()

    from project_locator import resolve_project_root

    workspace = tmp_path / "claude-workspace"
    project_root = _make_project(workspace / "Claude书")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(workspace))

    resolved = resolve_project_root(cwd=elsewhere)
    assert resolved == project_root.resolve()


def test_project_locator_user_home_prefers_webnovel_home_over_codex_home(monkeypatch, tmp_path):
    _ensure_scripts_on_path()

    from project_locator import _get_user_claude_root

    webnovel_home = tmp_path / "webnovel-home"
    codex_home = tmp_path / "codex-home"

    monkeypatch.delenv("WEBNOVEL_CLAUDE_HOME", raising=False)
    monkeypatch.setenv("WEBNOVEL_HOME", str(webnovel_home))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert _get_user_claude_root() == webnovel_home.resolve()


def test_project_locator_user_home_accepts_codex_home(monkeypatch, tmp_path):
    _ensure_scripts_on_path()

    from project_locator import _get_user_claude_root

    codex_home = tmp_path / "codex-home"

    monkeypatch.delenv("WEBNOVEL_CLAUDE_HOME", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert _get_user_claude_root() == codex_home.resolve()


def test_data_modules_config_user_home_accepts_codex_home(monkeypatch, tmp_path):
    _ensure_scripts_on_path()

    codex_home = tmp_path / "codex-home"

    monkeypatch.delenv("WEBNOVEL_CLAUDE_HOME", raising=False)
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    import data_modules.config as config_module

    config_module = importlib.reload(config_module)
    assert config_module._get_user_claude_root() == codex_home.resolve()
