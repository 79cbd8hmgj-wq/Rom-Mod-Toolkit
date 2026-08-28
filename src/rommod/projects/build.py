"""Ordered, reproducible NDS project builds."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from ndspy import VERSION as NDSPY_VERSION

from rommod.core.atomic import atomic_write_bytes
from rommod.core.hashes import sha256_file
from rommod.core.paths import resolve_inside
from rommod.errors import BuildError, TargetNotFoundError
from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.bytepatch import apply_byte_change
from rommod.platforms.nds.filesystem import replace_file
from rommod.platforms.nds.overlays import get_overlay_raw
from rommod.platforms.nds.rom import NdsRom
from rommod.platforms.nds.validation import validate_nds_bytes
from rommod.projects.manifest import (
    BytePatchChange,
    Change,
    FileReplaceChange,
    ProjectManifest,
    load_manifest,
)
from rommod.projects.project import verify_source


@dataclass(frozen=True)
class BuildResult:
    output_path: Path
    source_sha256: str
    output_sha256: str
    report_path: Path


def _clean_work_dir(project: Path) -> Path:
    work = resolve_inside(project, "build/work")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    return work


def _normalized_file_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        raise TargetNotFoundError("NitroFS target is empty")
    return normalized


def _read_target(rom: NdsRom, target: str) -> bytes:
    if target in ("arm9", "arm7"):
        return get_main_binary(rom, target)
    if target.startswith("overlay9:"):
        raw_id = target[len("overlay9:") :]
        if not raw_id.isdecimal():
            raise TargetNotFoundError(f"Invalid overlay target: {target}")
        return get_overlay_raw(rom, "arm9", int(raw_id))
    if target.startswith("overlay7:"):
        raw_id = target[len("overlay7:") :]
        if not raw_id.isdecimal():
            raise TargetNotFoundError(f"Invalid overlay target: {target}")
        return get_overlay_raw(rom, "arm7", int(raw_id))
    if target.startswith("file:"):
        path = _normalized_file_path(target[len("file:") :])
    else:
        path = _normalized_file_path(target)
    try:
        return bytes(rom._nds.getFileByName(path))
    except ValueError as exc:
        raise TargetNotFoundError(f"NitroFS file not found: {path}") from exc


def _canonical_target(change: Change) -> str:
    if isinstance(change, FileReplaceChange):
        return f"file:{_normalized_file_path(change.target)}"
    if isinstance(change, BytePatchChange):
        return change.target
    raise BuildError(f"Unsupported change object: {type(change).__name__}")


def _apply_change(rom: NdsRom, project: Path, change: Change) -> None:
    if isinstance(change, FileReplaceChange):
        source_path = resolve_inside(project, change.source)
        if not source_path.is_file():
            raise BuildError(f"Replacement file does not exist: {change.source}")
        replace_file(rom, change.target, source_path.read_bytes())
        return
    if isinstance(change, BytePatchChange):
        apply_byte_change(rom, change)
        return
    raise BuildError(f"Unsupported change object: {type(change).__name__}")


def _snapshot_touched_targets(rom: NdsRom, manifest: ProjectManifest) -> dict[str, bytes]:
    targets: dict[str, bytes] = {}
    for change in manifest.changes:
        target = _canonical_target(change)
        targets[target] = _read_target(rom, target)
    return targets


def _verify_touched_targets(rebuilt: NdsRom, expected: dict[str, bytes]) -> None:
    for target, expected_bytes in expected.items():
        actual = _read_target(rebuilt, target)
        if actual != expected_bytes:
            raise BuildError(f"Rebuilt target does not contain declared changes: {target}")


def _change_report(change: Change) -> dict[str, object]:
    if isinstance(change, FileReplaceChange):
        return {"type": change.type, "target": change.target, "source": change.source}
    if isinstance(change, BytePatchChange):
        return {
            "type": change.type,
            "target": change.target,
            "offset": change.offset,
            "expected": change.expected.hex(" ").upper(),
            "replacement": change.replacement.hex(" ").upper(),
        }
    raise BuildError(f"Unsupported change object: {type(change).__name__}")


def _write_report(
    project: Path,
    manifest: ProjectManifest,
    output_bytes: bytes,
    output_sha256: str,
) -> Path:
    report_path = resolve_inside(project, "reports/build.json")
    report = {
        "schema_version": 1,
        "platform": "nds",
        "source_sha256": manifest.source.sha256,
        "output_sha256": output_sha256,
        "output_size": len(output_bytes),
        "changes": [_change_report(change) for change in manifest.changes],
        "validation": {"parse_reload": True, "declared_changes": True},
        "tools": {
            "ndspy": f"{NDSPY_VERSION.major}.{NDSPY_VERSION.minor}.{NDSPY_VERSION.patch}"
        },
    }
    atomic_write_bytes(
        report_path,
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return report_path


def build_project(project_dir: Path) -> BuildResult:
    project = Path(project_dir).resolve()
    manifest = load_manifest(project)
    source = verify_source(project, manifest)
    rom = NdsRom.load(source)
    _clean_work_dir(project)

    for change in manifest.changes:
        _apply_change(rom, project, change)

    expected_targets = _snapshot_touched_targets(rom, manifest)
    output_bytes = rom.serialize()
    validate_nds_bytes(output_bytes)
    rebuilt = NdsRom.from_bytes(output_bytes)
    _verify_touched_targets(rebuilt, expected_targets)

    output_path = resolve_inside(project, manifest.output.rom)
    atomic_write_bytes(output_path, output_bytes)
    output_sha256 = sha256_file(output_path)
    report_path = _write_report(project, manifest, output_bytes, output_sha256)
    return BuildResult(output_path, manifest.source.sha256, output_sha256, report_path)
