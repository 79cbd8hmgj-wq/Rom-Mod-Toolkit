"""Unified native build wrapper for discovered source projects."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rommod.core.atomic import atomic_write_bytes
from rommod.discovery.scanner import scan_project, write_scan_reports
from rommod.errors import BuildError


@dataclass(frozen=True)
class SourceBuildResult:
    root: Path
    build_system: str
    command: tuple[str, ...]
    outputs: tuple[str, ...]
    report_path: Path


def _write_report(result: SourceBuildResult) -> None:
    payload = {
        "schema_version": 1,
        "mode": "source",
        "success": True,
        "root": str(result.root),
        "build_system": result.build_system,
        "command": list(result.command),
        "outputs": list(result.outputs),
    }
    atomic_write_bytes(
        result.report_path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def build_source_project(root: Path) -> SourceBuildResult:
    """Build a discovered source project using its native build system."""

    resolved = Path(root).resolve()
    before = scan_project(resolved)
    if before.build_system != "make":
        raise BuildError(
            f"unsupported or undetected native build system for source project: {before.build_system!r}"
        )

    command = ("make",)
    try:
        completed = subprocess.run(
            command,
            cwd=resolved,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise BuildError(f"failed to launch native build command: {command[0]}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        suffix = f": {detail}" if detail else ""
        raise BuildError(f"native build failed with exit code {completed.returncode}{suffix}")

    after = scan_project(resolved)
    write_scan_reports(after)
    if not after.rom_outputs:
        raise BuildError("native build completed successfully but produced no .nds output")

    result = SourceBuildResult(
        root=resolved,
        build_system="make",
        command=command,
        outputs=after.rom_outputs,
        report_path=resolved / "rommod" / "reports" / "build.json",
    )
    _write_report(result)
    return result
