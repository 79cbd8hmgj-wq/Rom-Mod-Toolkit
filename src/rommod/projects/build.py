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
from rommod.platforms.nds.assembler import ArmipsRunResult, run_armips_change
from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.bytepatch import apply_byte_change
from rommod.platforms.nds.c_injection import CInjectionRunResult, run_c_inject_change
from rommod.platforms.nds.filesystem import replace_file
from rommod.platforms.nds.injection import InjectionRunResult, run_inject_change
from rommod.platforms.nds.overlays import get_overlay_raw
from rommod.platforms.nds.rom import NdsRom
from rommod.platforms.nds.validation import validate_nds_bytes
from rommod.projects.manifest import (
    ArmipsChange,
    BytePatchChange,
    Change,
    CInjectChange,
    FileReplaceChange,
    InjectChange,
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
    if isinstance(change, ArmipsChange):
        return change.target
    if isinstance(change, InjectChange):
        return change.target
    if isinstance(change, CInjectChange):
        return change.target
    raise BuildError(f"Unsupported change object: {type(change).__name__}")


def _apply_change(
    rom: NdsRom,
    project: Path,
    manifest: ProjectManifest,
    change: Change,
    index: int,
) -> ArmipsRunResult | InjectionRunResult | CInjectionRunResult | None:
    if isinstance(change, FileReplaceChange):
        source_path = resolve_inside(project, change.source)
        if not source_path.is_file():
            raise BuildError(f"Replacement file does not exist: {change.source}")
        replace_file(rom, change.target, source_path.read_bytes())
        return None
    if isinstance(change, BytePatchChange):
        apply_byte_change(rom, change)
        return None
    if isinstance(change, ArmipsChange):
        return run_armips_change(
            rom,
            project,
            change,
            manifest.tools.armips,
            index,
        )
    if isinstance(change, InjectChange):
        return run_inject_change(
            rom,
            project,
            change,
            manifest.tools.armips,
            index,
        )
    if isinstance(change, CInjectChange):
        return run_c_inject_change(
            rom,
            project,
            change,
            manifest.tools,
            index,
        )
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
    if isinstance(change, ArmipsChange):
        result: dict[str, object] = {
            "type": change.type,
            "target": change.target,
            "script": change.script,
        }
        if change.symbols is not None:
            result["symbols"] = change.symbols
        if change.symbol_file is not None:
            result["symbol_file"] = change.symbol_file
        if change.symbol_component is not None:
            result["symbol_component"] = change.symbol_component
        return result
    if isinstance(change, CInjectChange):
        result = {
            "type": change.type,
            "target": change.target,
            "symbol_file": change.symbol_file,
            "hook": change.hook,
            "expected": change.expected.hex(" ").upper(),
            "cave": change.cave,
            "reserve": change.reserve,
            "fill": f"{change.fill:02X}",
        }
        if change.source is not None:
            result["source"] = change.source
        else:
            result["sources"] = list(change.sources)
        if change.symbol_component is not None:
            result["symbol_component"] = change.symbol_component
        return result
    if isinstance(change, InjectChange):
        result = {
            "type": change.type,
            "target": change.target,
            "symbol_file": change.symbol_file,
            "hook": change.hook,
            "expected": change.expected.hex(" ").upper(),
            "script": change.script,
            "cave": change.cave,
            "reserve": change.reserve,
            "fill": f"{change.fill:02X}",
        }
        if change.symbols is not None:
            result["symbols"] = change.symbols
        if change.symbol_component is not None:
            result["symbol_component"] = change.symbol_component
        if change.scratch_register is not None:
            result["scratch_register"] = change.scratch_register
        return result
    raise BuildError(f"Unsupported change object: {type(change).__name__}")


def _write_report(
    project: Path,
    manifest: ProjectManifest,
    output_bytes: bytes,
    output_sha256: str,
    assembly_runs: list[ArmipsRunResult | InjectionRunResult | CInjectionRunResult],
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
    injection_runs = [run for run in assembly_runs if isinstance(run, InjectionRunResult)]
    if injection_runs:
        report["injections"] = [
            {
                "target": run.target,
                "hook_address": run.hook_address,
                "cave_address": run.cave_address,
                "reserve": run.reserve,
                "hook_mode": run.hook_mode,
                "hook_size": run.hook_size,
                "scratch_register": run.scratch_register,
            }
            for run in injection_runs
        ]
    c_injection_runs = [run for run in assembly_runs if isinstance(run, CInjectionRunResult)]
    if c_injection_runs:
        report["c_injections"] = [
            {
                "target": run.target,
                "hook_address": run.hook_address,
                "cave_address": run.cave_address,
                "code_address": run.code_address,
                "reserve": run.reserve,
                "payload_size": run.payload_size,
                "thumb_interworking": run.thumb_interworking,
            }
            for run in c_injection_runs
        ]
        c_run = c_injection_runs[-1]
        report["tools"]["clang"] = {"path": str(c_run.clang), "version": c_run.clang_version}
        report["tools"]["ld_lld"] = {"path": str(c_run.ld_lld), "version": c_run.lld_version}
        report["tools"]["llvm_objcopy"] = {
            "path": str(c_run.llvm_objcopy),
            "version": c_run.objcopy_version,
        }
    if assembly_runs:
        run = assembly_runs[-1]
        report["tools"]["armips"] = {
            "path": str(run.executable),
            "version": run.version,
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

    assembly_runs: list[ArmipsRunResult | InjectionRunResult | CInjectionRunResult] = []
    for index, change in enumerate(manifest.changes):
        assembly_run = _apply_change(rom, project, manifest, change, index)
        if assembly_run is not None:
            assembly_runs.append(assembly_run)

    expected_targets = _snapshot_touched_targets(rom, manifest)
    output_bytes = rom.serialize()
    validate_nds_bytes(output_bytes)
    rebuilt = NdsRom.from_bytes(output_bytes)
    _verify_touched_targets(rebuilt, expected_targets)

    for assembly_run in assembly_runs:
        if assembly_run.symbol_destination is not None and assembly_run.symbol_bytes is not None:
            atomic_write_bytes(assembly_run.symbol_destination, assembly_run.symbol_bytes)

    output_path = resolve_inside(project, manifest.output.rom)
    atomic_write_bytes(output_path, output_bytes)
    output_sha256 = sha256_file(output_path)
    report_path = _write_report(project, manifest, output_bytes, output_sha256, assembly_runs)
    return BuildResult(output_path, manifest.source.sha256, output_sha256, report_path)
