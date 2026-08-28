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


def resolve_executable(
    project_dir: Path,
    configured: str | None,
    *,
    env_name: str,
    program: str,
    label: str | None = None,
) -> Path:
    project = Path(project_dir).resolve()
    display = label or program
    if configured is not None:
        raw = Path(configured).expanduser()
        if raw.is_absolute():
            candidate = Path(os.path.abspath(str(raw)))
        else:
            unresolved = project / raw
            resolve_inside(project, raw)
            candidate = Path(os.path.abspath(str(unresolved)))
        if not _usable_executable(candidate):
            raise ExternalToolError(f"Configured {display} executable is not usable: {candidate}")
        return candidate

    env_value = os.environ.get(env_name)
    if env_value:
        candidate = Path(os.path.abspath(os.path.expanduser(env_value)))
        if not _usable_executable(candidate):
            raise ExternalToolError(f"{env_name} does not point to a usable executable: {candidate}")
        return candidate

    discovered = shutil.which(program)
    if discovered:
        return Path(os.path.abspath(discovered))
    raise ExternalToolError(
        f"{display} executable not found; configure its tools entry, {env_name}, or PATH"
    )


def resolve_armips(project_dir: Path, configured: str | None) -> Path:
    return resolve_executable(
        project_dir,
        configured,
        env_name="ROMMOD_ARMIPS",
        program="armips",
        label="armips",
    )


def resolve_clang(project_dir: Path, configured: str | None) -> Path:
    return resolve_executable(
        project_dir,
        configured,
        env_name="ROMMOD_CLANG",
        program="clang",
        label="clang",
    )


def resolve_ld_lld(project_dir: Path, configured: str | None) -> Path:
    return resolve_executable(
        project_dir,
        configured,
        env_name="ROMMOD_LD_LLD",
        program="ld.lld",
        label="ld.lld",
    )


def resolve_llvm_objcopy(project_dir: Path, configured: str | None) -> Path:
    return resolve_executable(
        project_dir,
        configured,
        env_name="ROMMOD_LLVM_OBJCOPY",
        program="llvm-objcopy",
        label="llvm-objcopy",
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


def probe_version(executable: Path, *args: str) -> str:
    result = run_capture([executable, *args])
    output = (result.stdout + "\n" + result.stderr).strip().splitlines()
    return output[0].strip() if output else "unknown"


def probe_armips_version(executable: Path) -> str:
    result = run_capture([executable])
    output = (result.stdout + "\n" + result.stderr).strip().splitlines()
    if output and output[0].lower().startswith("armips assembler v"):
        return output[0].strip()
    return "unknown"
