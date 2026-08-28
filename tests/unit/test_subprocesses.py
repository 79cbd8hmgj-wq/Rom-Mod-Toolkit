from __future__ import annotations

import os
from pathlib import Path

import pytest

from rommod.core.subprocesses import resolve_armips
from rommod.errors import ExternalToolError


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)
    return path


def test_resolve_armips_prefers_project_configuration(tmp_path: Path, monkeypatch):
    configured = _make_executable(tmp_path / "tools/armips")
    monkeypatch.setenv("ROMMOD_ARMIPS", str(_make_executable(tmp_path / "env-armips")))
    assert resolve_armips(tmp_path, "tools/armips") == configured.resolve()


def test_resolve_armips_uses_environment(tmp_path: Path, monkeypatch):
    executable = _make_executable(tmp_path / "armips-env")
    monkeypatch.setenv("ROMMOD_ARMIPS", str(executable))
    assert resolve_armips(tmp_path, None) == executable.resolve()


def test_resolve_armips_rejects_missing_tool(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ROMMOD_ARMIPS", raising=False)
    monkeypatch.setenv("PATH", "")
    with pytest.raises(ExternalToolError, match="armips"):
        resolve_armips(tmp_path, None)
