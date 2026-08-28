"""Symbol-aware, bounded ARM hook injection for NDS code targets."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from rommod.core.paths import resolve_inside
from rommod.core.subprocesses import probe_armips_version, resolve_armips, run_capture
from rommod.errors import BuildError, ExternalToolError, PatchMismatchError
from rommod.platforms.nds.addresses import CpuAddress, FileOffset, cpu_to_file_offset, file_offset_to_cpu
from rommod.platforms.nds.assembler import _imported_symbol_directives, _target_state, validate_armips_fragment
from rommod.platforms.nds.rom import NdsRom
from rommod.platforms.nds.symbols import load_symbol_table
from rommod.projects.manifest import InjectChange


_INJECTION_POSITION_OR_MODE = re.compile(r"(?im)^\s*\.(?:org|orga|arm|thumb)\b")
_RESERVED_LABEL = re.compile(r"(?i)\b__rommod_[A-Za-z0-9_]*")


@dataclass(frozen=True)
class InjectionRunResult:
    target: str
    executable: Path
    version: str
    symbol_bytes: bytes | None
    symbol_destination: Path | None
    hook_address: int
    cave_address: int
    reserve: int


def validate_injection_fragment(source: str) -> None:
    try:
        validate_armips_fragment(source)
    except ExternalToolError as exc:
        raise ExternalToolError(f"injection fragment is not allowed: {exc}") from exc
    match = _INJECTION_POSITION_OR_MODE.search(source) or _RESERVED_LABEL.search(source)
    if match:
        raise ExternalToolError(
            f"injection fragment construct {match.group(0)!r} is not allowed; "
            "the toolkit owns hook/cave positions and ARM mode"
        )


def find_trailing_fill_cave(
    data: bytes,
    *,
    reserve: int,
    fill: int = 0,
    alignment: int = 4,
) -> FileOffset:
    if reserve <= 0:
        raise BuildError("code-cave reserve must be positive")
    if alignment <= 0:
        raise BuildError("code-cave alignment must be positive")
    if fill < 0 or fill > 0xFF:
        raise BuildError("code-cave fill must be a byte")

    run_start = len(data)
    while run_start > 0 and data[run_start - 1] == fill:
        run_start -= 1
    aligned = ((run_start + alignment - 1) // alignment) * alignment
    if aligned + reserve > len(data):
        raise BuildError(
            f"no trailing 0x{fill:02X} code cave of {reserve} bytes aligned to {alignment}"
        )
    return FileOffset(aligned)


def _select_hook(project: Path, change: InjectChange, region):
    table = load_symbol_table(resolve_inside(project, change.symbol_file))
    component = change.symbol_component or change.target
    matches = table.by_name(change.hook, component=component)
    if not matches:
        raise ExternalToolError(
            f"hook symbol {change.hook!r} not found in component {component!r}"
        )
    if len(matches) != 1:
        raise ExternalToolError(
            f"hook symbol {change.hook!r} is ambiguous in component {component!r}"
        )
    symbol = matches[0]
    if symbol.instruction_set != "arm":
        raise ExternalToolError(
            f"hook symbol {change.hook!r} uses {symbol.instruction_set!r}; "
            "this injection slice supports ARM hooks only"
        )
    expected_offset = symbol.address - region.ram_address.value
    if expected_offset != symbol.offset:
        raise ExternalToolError(
            f"hook symbol {change.hook!r} offset 0x{symbol.offset:X} does not match "
            f"runtime address 0x{symbol.address:08X} (expected offset 0x{expected_offset:X})"
        )
    hook_offset = cpu_to_file_offset(region, CpuAddress(symbol.address))
    return symbol, hook_offset


def _ranges_overlap(a_start: int, a_size: int, b_start: int, b_size: int) -> bool:
    return a_start < b_start + b_size and b_start < a_start + a_size


def run_inject_change(
    rom: NdsRom,
    project_dir: Path,
    change: InjectChange,
    configured_executable: str | None,
    job_index: int,
) -> InjectionRunResult:
    project = Path(project_dir).resolve()
    executable = resolve_armips(project, configured_executable)
    script_path = resolve_inside(project, change.script)
    if not script_path.is_file():
        raise BuildError(f"injection script does not exist: {change.script}")
    source = script_path.read_text(encoding="utf-8")
    validate_injection_fragment(source)

    architecture, region, original, setter = _target_state(rom, change.target)
    hook_symbol, hook_offset = _select_hook(project, change, region)
    if len(change.expected) != 4:
        raise PatchMismatchError("ARM hook expected bytes must be exactly 4 bytes")
    actual = original[hook_offset.value : hook_offset.value + 4]
    if actual != change.expected:
        raise PatchMismatchError(
            f"expected bytes {change.expected.hex(' ').upper()} at 0x{hook_offset.value:X}, "
            f"found {actual.hex(' ').upper()}"
        )

    if change.cave == "auto":
        cave_offset = find_trailing_fill_cave(
            original, reserve=change.reserve, fill=change.fill, alignment=4
        )
    else:
        cave_offset = cpu_to_file_offset(region, CpuAddress(change.cave))
    if cave_offset.value + change.reserve > len(original):
        raise BuildError("code-cave reserve extends outside target")
    cave_bytes = original[cave_offset.value : cave_offset.value + change.reserve]
    if cave_bytes != bytes([change.fill]) * change.reserve:
        raise BuildError(
            f"code cave at 0x{cave_offset.value:X} does not match fill byte 0x{change.fill:02X}"
        )
    if _ranges_overlap(hook_offset.value, 4, cave_offset.value, change.reserve):
        raise BuildError("hook range overlaps reserved code cave")

    cave_address = file_offset_to_cpu(region, cave_offset).value
    return_address = hook_symbol.address + 4
    imported = _imported_symbol_directives(project, change, region)

    work_root = resolve_inside(project, "build/work/inject")
    job_dir = work_root / f"{job_index:04d}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    target_path = job_dir / "target.bin"
    payload_path = job_dir / "payload.asm"
    driver_path = job_dir / "driver.asm"
    trace_path = job_dir / "trace.txt"
    symbol_path = job_dir / "symbols.sym"
    target_path.write_bytes(original)
    payload_path.write_text(source, encoding="utf-8")

    payload_label = f"__rommod_payload_{job_index:04d}"
    driver_path.write_text(
        architecture
        + f'.open "target.bin",0x{region.ram_address.value:08X}\n'
        + imported
        + f".org 0x{hook_symbol.address:08X}\n"
        + f"b {payload_label}\n"
        + f".org 0x{cave_address:08X}\n"
        + f"{payload_label}:\n"
        + '.include "payload.asm"\n'
        + f"b 0x{return_address:08X}\n"
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
            f"armips injection failed for {change.target} with exit code "
            f"{result.returncode}: {diagnostics}"
        )

    patched = target_path.read_bytes()
    if len(patched) != len(original):
        raise ExternalToolError(
            f"armips injection changed {change.target} size from {len(original)} to {len(patched)} bytes"
        )
    for offset, (before, after) in enumerate(zip(original, patched)):
        if before == after:
            continue
        in_hook = hook_offset.value <= offset < hook_offset.value + 4
        in_cave = cave_offset.value <= offset < cave_offset.value + change.reserve
        if not (in_hook or in_cave):
            raise ExternalToolError(
                f"armips injection wrote outside hook/cave at target offset 0x{offset:X}"
            )
    setter(patched)

    symbol_bytes = None
    symbol_destination = None
    if change.symbols is not None:
        if not symbol_path.is_file():
            raise ExternalToolError("armips injection did not produce requested symbol file")
        symbol_bytes = symbol_path.read_bytes()
        symbol_destination = resolve_inside(project, change.symbols)

    return InjectionRunResult(
        target=change.target,
        executable=executable,
        version=probe_armips_version(executable),
        symbol_bytes=symbol_bytes,
        symbol_destination=symbol_destination,
        hook_address=hook_symbol.address,
        cave_address=cave_address,
        reserve=change.reserve,
    )
