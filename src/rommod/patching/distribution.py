"""Create, verify, and report distributable binary patches."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from rommod.core.atomic import atomic_write_bytes
from rommod.core.hashes import sha256_file
from rommod.core.paths import resolve_inside
from rommod.core.subprocesses import (
    probe_version,
    resolve_flips,
    resolve_xdelta3,
    run_capture,
)
from rommod.errors import BuildError, ExternalToolError
from rommod.projects.build import build_project
from rommod.projects.manifest import ToolsConfig, load_manifest
from rommod.projects.project import verify_source


PatchFormat = Literal["bps", "ips", "xdelta"]
_SUPPORTED_FORMATS = {"bps", "ips", "xdelta"}


@dataclass(frozen=True)
class PatchResult:
    output_path: Path
    patch_format: PatchFormat
    source_sha256: str
    target_sha256: str
    patch_sha256: str
    patch_size: int
    verified: bool
    tool: Path
    tool_version: str
    report_path: Path | None = None


def _normalize_format(value: str) -> PatchFormat:
    lowered = value.lower()
    if lowered not in _SUPPORTED_FORMATS:
        raise BuildError(
            f"Unsupported patch format {value!r}; expected one of: bps, ips, xdelta"
        )
    return lowered  # type: ignore[return-value]


def _require_file(path: Path, label: str) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise BuildError(f"{label} file does not exist: {path}")
    return resolved


def _require_success(result, stage: str) -> None:
    if result.returncode == 0:
        return
    diagnostics = (result.stdout + "\n" + result.stderr).strip()
    raise ExternalToolError(
        f"{stage} failed with exit code {result.returncode}: {diagnostics}"
    )


def _flips_commands(
    executable: Path,
    patch_format: PatchFormat,
    source: Path,
    target: Path,
    patch: Path,
    decoded: Path,
) -> tuple[list[Path | str], list[Path | str]]:
    format_flag = "--bps" if patch_format == "bps" else "--ips"
    create: list[Path | str] = [executable, "--create"]
    if patch_format == "bps":
        create.append("--exact")
    create.extend([format_flag, source, target, patch])

    apply: list[Path | str] = [executable, "--apply"]
    if patch_format == "bps":
        apply.append("--exact")
    apply.extend([patch, source, decoded])
    return create, apply


def _xdelta_commands(
    executable: Path,
    source: Path,
    target: Path,
    patch: Path,
    decoded: Path,
) -> tuple[list[Path | str], list[Path | str]]:
    return (
        [executable, "-9", "-e", "-f", "-s", source, target, patch],
        [executable, "-d", "-f", "-s", source, patch, decoded],
    )


def generate_binary_patch(
    project_dir: Path,
    source: Path,
    target: Path,
    *,
    patch_format: str,
    output: Path,
    tools: ToolsConfig,
) -> PatchResult:
    """Create a patch, re-apply it, and publish only after byte-equivalent verification."""

    project = Path(project_dir).resolve()
    fmt = _normalize_format(patch_format)
    source_path = _require_file(source, "Patch source")
    target_path = _require_file(target, "Patch target")
    output_path = resolve_inside(project, output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = resolve_inside(project, f"build/work/patch/{fmt}")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    temp_patch = work_dir / f"patch.{fmt}"
    decoded = work_dir / "decoded-target.bin"

    if fmt in ("bps", "ips"):
        executable = resolve_flips(project, tools.flips)
        create_command, apply_command = _flips_commands(
            executable, fmt, source_path, target_path, temp_patch, decoded
        )
        version = probe_version(executable, "--version")
        tool_name = "Flips"
    else:
        executable = resolve_xdelta3(project, tools.xdelta3)
        create_command, apply_command = _xdelta_commands(
            executable, source_path, target_path, temp_patch, decoded
        )
        version = probe_version(executable, "-V")
        tool_name = "xdelta3"

    create_result = run_capture(create_command, cwd=work_dir)
    _require_success(create_result, f"{tool_name} patch creation")
    if not temp_patch.is_file() or temp_patch.stat().st_size == 0:
        raise ExternalToolError(f"{tool_name} completed without producing a patch")

    apply_result = run_capture(apply_command, cwd=work_dir)
    _require_success(apply_result, f"{tool_name} patch verification")
    if not decoded.is_file():
        raise ExternalToolError(f"{tool_name} verification did not produce decoded output")

    source_sha256 = sha256_file(source_path)
    target_sha256 = sha256_file(target_path)
    decoded_sha256 = sha256_file(decoded)
    if decoded.stat().st_size != target_path.stat().st_size or decoded_sha256 != target_sha256:
        raise ExternalToolError(
            f"{tool_name} verification output does not match the rebuilt target"
        )

    atomic_write_bytes(output_path, temp_patch.read_bytes())
    patch_sha256 = sha256_file(output_path)
    return PatchResult(
        output_path=output_path,
        patch_format=fmt,
        source_sha256=source_sha256,
        target_sha256=target_sha256,
        patch_sha256=patch_sha256,
        patch_size=output_path.stat().st_size,
        verified=True,
        tool=executable,
        tool_version=version,
    )


def create_project_patch(
    project_dir: Path,
    patch_format: str,
    output: Path | None = None,
) -> PatchResult:
    """Rebuild a project and create a verified distributable patch against its locked source."""

    project = Path(project_dir).resolve()
    fmt = _normalize_format(patch_format)
    manifest = load_manifest(project)
    source = verify_source(project, manifest)
    build = build_project(project)

    if output is None:
        default_relative = Path(manifest.output.rom).with_suffix(f".{fmt}")
        output_path = resolve_inside(project, default_relative)
    else:
        output_path = resolve_inside(project, output)

    result = generate_binary_patch(
        project,
        source,
        build.output_path,
        patch_format=fmt,
        output=output_path,
        tools=manifest.tools,
    )

    report_path = resolve_inside(project, f"reports/patch-{fmt}.json")
    report = {
        "schema_version": 1,
        "format": fmt,
        "output": str(result.output_path.relative_to(project)).replace("\\", "/"),
        "patch_size": result.patch_size,
        "patch_sha256": result.patch_sha256,
        "source_sha256": result.source_sha256,
        "target_sha256": result.target_sha256,
        "verified": result.verified,
        "build_report": str(build.report_path.relative_to(project)).replace("\\", "/"),
        "tool": {
            "path": str(result.tool),
            "version": result.tool_version,
        },
    }
    atomic_write_bytes(
        report_path,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return replace(result, report_path=report_path)
