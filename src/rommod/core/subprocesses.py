"""External-tool discovery and captured subprocess execution."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rommod.core.paths import resolve_inside
from rommod.errors import ExternalToolError


@dataclass(frozen=True)
class ProcessResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


def _usable_executable(path: Path) -> bool:
    if not path.is_file():
        return False
    return os.name == "nt" or os.access(path, os.X_OK)


def resolve_armips(project_dir: Path, configured: str | None) -> Path:
    project = Path(project_dir).resolve()
    if configured is not None:
        raw = Path(configured)
        candidate = raw.resolve() if raw.is_absolute() else resolve_inside(project, raw)
        if not _usable_executable(candidate):
            raise ExternalToolError(f"Configured armips executable is not usable: {candidate}")
        return candidate

    env_value = os.environ.get("ROMMOD_ARMIPS")
    if env_value:
        candidate = Path(env_value).expanduser().resolve()
        if not _usable_executable(candidate):
            raise ExternalToolError(f"ROMMOD_ARMIPS does not point to a usable executable: {candidate}")
        return candidate

    discovered = shutil.which("armips")
    if discovered:
        return Path(discovered).resolve()
    raise ExternalToolError(
        "armips executable not found; configure tools.armips, ROMMOD_ARMIPS, or PATH"
    )


def run_capture(argv: Sequence[str | Path], cwd: Path | None = None) -> ProcessResult:
    args = tuple(str(value) for value in argv)
    try:
        completed = subprocess.run(
            args,
            cwd=None if cwd is None else str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise ExternalToolError(f"Could not execute {args[0]}: {exc}") from exc
    return ProcessResult(args, completed.returncode, completed.stdout, completed.stderr)


def probe_armips_version(executable: Path) -> str:
    result = run_capture([executable])
    output = (result.stdout + "\n" + result.stderr).strip().splitlines()
    if output and output[0].lower().startswith("armips assembler v"):
        return output[0].strip()
    return "unknown"
