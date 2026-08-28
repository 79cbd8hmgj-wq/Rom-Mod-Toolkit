"""Safe armips jobs for NDS ARM9/ARM7 and overlay targets."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from rommod.core.paths import resolve_inside
from rommod.core.subprocesses import probe_armips_version, resolve_armips, run_capture
from rommod.errors import BuildError, ExternalToolError, TargetNotFoundError
from rommod.platforms.nds.addresses import region_for_main, region_for_overlay
from rommod.platforms.nds.binaries import get_main_binary, set_main_binary
from rommod.platforms.nds.overlays import get_overlay_raw, set_overlay_raw
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.manifest import ArmipsChange


_FORBIDDEN_DIRECTIVE = re.compile(
    r"(?im)^\s*\.?(?:open|openfile|create|createfile|close|closefile|loadelf|include|headersize)\b"
)
_FORBIDDEN_ARCHITECTURE = re.compile(
    r"(?im)^\s*\.(?:nds|gba|psp|psx|ps2|n64|rsp|3ds|saturn|32x|arm\.big|arm\.little)\b"
)


@dataclass(frozen=True)
class ArmipsRunResult:
    target: str
    executable: Path
    version: str
    symbol_bytes: bytes | None
    symbol_destination: Path | None


def validate_armips_fragment(source: str) -> None:
    match = _FORBIDDEN_DIRECTIVE.search(source) or _FORBIDDEN_ARCHITECTURE.search(source)
    if match:
        token = match.group(0).strip().split()[0]
        raise ExternalToolError(
            f"armips fragment directive {token!r} is not allowed; the toolkit owns target files and architecture"
        )


def _parse_overlay_id(target: str, prefix: str) -> int:
    value = target[len(prefix) :]
    if not value.isdecimal():
        raise TargetNotFoundError(f"Invalid armips overlay target: {target}")
    return int(value, 10)


def _target_state(rom: NdsRom, target: str):
    if target == "arm9":
        region = region_for_main(rom, "arm9")
        return ".nds\n.arm\n", region.ram_address.value, get_main_binary(rom, "arm9"), (
            lambda data: set_main_binary(rom, "arm9", data)
        )
    if target == "arm7":
        region = region_for_main(rom, "arm7")
        return ".gba\n.arm\n", region.ram_address.value, get_main_binary(rom, "arm7"), (
            lambda data: set_main_binary(rom, "arm7", data)
        )
    if target.startswith("overlay9:"):
        overlay_id = _parse_overlay_id(target, "overlay9:")
        region = region_for_overlay(rom, "arm9", overlay_id)
        return ".nds\n.arm\n", region.ram_address.value, get_overlay_raw(rom, "arm9", overlay_id), (
            lambda data: set_overlay_raw(rom, "arm9", overlay_id, data)
        )
    if target.startswith("overlay7:"):
        overlay_id = _parse_overlay_id(target, "overlay7:")
        region = region_for_overlay(rom, "arm7", overlay_id)
        return ".gba\n.arm\n", region.ram_address.value, get_overlay_raw(rom, "arm7", overlay_id), (
            lambda data: set_overlay_raw(rom, "arm7", overlay_id, data)
        )
    raise TargetNotFoundError(f"Unsupported armips target: {target}")


def run_armips_change(
    rom: NdsRom,
    project_dir: Path,
    change: ArmipsChange,
    configured_executable: str | None,
    job_index: int,
) -> ArmipsRunResult:
    project = Path(project_dir).resolve()
    executable = resolve_armips(project, configured_executable)
    script_path = resolve_inside(project, change.script)
    if not script_path.is_file():
        raise BuildError(f"armips script does not exist: {change.script}")
    source = script_path.read_text(encoding="utf-8")
    validate_armips_fragment(source)

    architecture, ram_base, original, setter = _target_state(rom, change.target)
    work_root = resolve_inside(project, "build/work/armips")
    job_dir = work_root / f"{job_index:04d}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    target_path = job_dir / "target.bin"
    fragment_path = job_dir / "fragment.asm"
    driver_path = job_dir / "driver.asm"
    trace_path = job_dir / "trace.txt"
    symbol_path = job_dir / "symbols.sym"
    target_path.write_bytes(original)
    fragment_path.write_text(source, encoding="utf-8")
    driver_path.write_text(
        architecture
        + f'.open "target.bin",0x{ram_base:08X}\n'
        + '.include "fragment.asm"\n'
        + ".close\n",
        encoding="utf-8",
    )

    argv: list[str | Path] = [
        executable,
        "driver.asm",
        "-erroronwarning",
        "-temp",
        trace_path.name,
    ]
    if change.symbols is not None:
        argv.extend(["-sym", symbol_path.name])
    result = run_capture(argv, cwd=job_dir)
    if result.returncode != 0:
        diagnostics = (result.stdout + "\n" + result.stderr).strip()
        raise ExternalToolError(
            f"armips failed for {change.target} with exit code {result.returncode}: {diagnostics}"
        )

    patched = target_path.read_bytes()
    if len(patched) != len(original):
        raise ExternalToolError(
            f"armips changed {change.target} size from {len(original)} to {len(patched)} bytes"
        )
    setter(patched)

    symbol_bytes = None
    symbol_destination = None
    if change.symbols is not None:
        if not symbol_path.is_file():
            raise ExternalToolError("armips completed without producing the requested symbol file")
        symbol_bytes = symbol_path.read_bytes()
        symbol_destination = resolve_inside(project, change.symbols)

    return ArmipsRunResult(
        target=change.target,
        executable=executable,
        version=probe_armips_version(executable),
        symbol_bytes=symbol_bytes,
        symbol_destination=symbol_destination,
    )
