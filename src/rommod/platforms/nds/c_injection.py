"""Guarded freestanding ARM C payload injection for NDS code targets."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from rommod.core.paths import resolve_inside
from rommod.core.subprocesses import probe_armips_version, resolve_armips, run_capture
from rommod.errors import BuildError, ExternalToolError
from rommod.platforms.nds.addresses import CpuAddress, cpu_to_file_offset, file_offset_to_cpu
from rommod.platforms.nds.assembler import _imported_symbol_directives, _target_state
from rommod.platforms.nds.c_compiler import CCompileResult, compile_arm_c_payload
from rommod.platforms.nds.injection import (
    _ranges_overlap,
    _require_expected,
    _select_hook,
    find_trailing_fill_cave,
)
from rommod.platforms.nds.rom import NdsRom
from rommod.platforms.nds.symbols import load_symbol_table
from rommod.projects.manifest import CInjectChange, ToolsConfig


@dataclass(frozen=True)
class CInjectionRunResult:
    target: str
    executable: Path
    version: str
    symbol_bytes: bytes | None
    symbol_destination: Path | None
    hook_address: int
    cave_address: int
    code_address: int
    reserve: int
    payload_size: int
    thumb_interworking: bool
    clang: Path
    clang_version: str
    ld_lld: Path
    lld_version: str
    llvm_objcopy: Path
    objcopy_version: str


def run_c_inject_change(
    rom: NdsRom,
    project_dir: Path,
    change: CInjectChange,
    tools: ToolsConfig,
    job_index: int,
) -> CInjectionRunResult:
    project = Path(project_dir).resolve()
    architecture, region, original, setter = _target_state(rom, change.target)
    hook_symbol, hook_offset = _select_hook(project, change, region)
    if hook_symbol.instruction_set != "arm":
        raise BuildError("c_inject currently supports ARM hook symbols only")
    _require_expected(original, hook_offset, change.expected, 4)

    if change.cave == "auto":
        cave_offset = find_trailing_fill_cave(
            original,
            reserve=change.reserve,
            fill=change.fill,
            alignment=4,
        )
    else:
        cave_offset = cpu_to_file_offset(region, CpuAddress(change.cave))
    if cave_offset.value + change.reserve > len(original):
        raise BuildError("C injection code-cave reserve extends outside target")
    cave_bytes = original[cave_offset.value : cave_offset.value + change.reserve]
    if cave_bytes != bytes([change.fill]) * change.reserve:
        raise BuildError(
            f"C injection code cave at 0x{cave_offset.value:X} does not match fill byte 0x{change.fill:02X}"
        )
    if _ranges_overlap(hook_offset.value, 4, cave_offset.value, change.reserve):
        raise BuildError("C injection hook range overlaps reserved code cave")
    if change.reserve <= 8:
        raise BuildError("C injection reserve must leave space after the 8-byte wrapper")

    cave_address = file_offset_to_cpu(region, cave_offset).value
    code_address = cave_address + 8

    imported = _imported_symbol_directives(project, change, region)
    table = load_symbol_table(resolve_inside(project, change.symbol_file))
    component = change.symbol_component or change.target
    component_symbols = table.for_component(component)
    link_symbols = {
        symbol.name: symbol.address
        for symbol in component_symbols
        if symbol.instruction_set != "thumb"
    }
    thumb_link_symbols = {
        symbol.name: symbol.address
        for symbol in component_symbols
        if symbol.instruction_set == "thumb"
    }

    compile_result: CCompileResult = compile_arm_c_payload(
        project,
        change.source,
        sources=change.sources,
        load_address=code_address,
        capacity=change.reserve - 8,
        tools=tools,
        job_index=job_index,
        link_symbols=link_symbols,
        thumb_link_symbols=thumb_link_symbols,
    )

    executable = resolve_armips(project, tools.armips)
    return_address = hook_symbol.address + 4

    work_root = resolve_inside(project, "build/work/c_inject")
    job_dir = work_root / f"{job_index:04d}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    target_path = job_dir / "target.bin"
    payload_path = job_dir / "payload.bin"
    driver_path = job_dir / "driver.asm"
    trace_path = job_dir / "trace.txt"
    target_path.write_bytes(original)
    payload_path.write_bytes(compile_result.binary)

    wrapper_label = f"__rommod_c_wrapper_{job_index:04d}"
    driver_path.write_text(
        architecture
        + f'.open "target.bin",0x{region.ram_address.value:08X}\n'
        + imported
        + f".org 0x{hook_symbol.address:08X}\n"
        + f"b {wrapper_label}\n"
        + f".org 0x{cave_address:08X}\n"
        + f"{wrapper_label}:\n"
        + f"bl 0x{code_address:08X}\n"
        + f"b 0x{return_address:08X}\n"
        + f".org 0x{code_address:08X}\n"
        + '.incbin "payload.bin"\n'
        + ".close\n",
        encoding="utf-8",
    )

    result = run_capture(
        [executable, "driver.asm", "-erroronwarning", "-temp", trace_path.name],
        cwd=job_dir,
    )
    if result.returncode != 0:
        diagnostics = (result.stdout + "\n" + result.stderr).strip()
        raise ExternalToolError(
            f"armips C injection failed for {change.target} with exit code "
            f"{result.returncode}: {diagnostics}"
        )

    patched = target_path.read_bytes()
    if len(patched) != len(original):
        raise ExternalToolError(
            f"C injection changed {change.target} size from {len(original)} to {len(patched)} bytes"
        )
    for offset, (before, after) in enumerate(zip(original, patched)):
        if before == after:
            continue
        in_hook = hook_offset.value <= offset < hook_offset.value + 4
        in_cave = cave_offset.value <= offset < cave_offset.value + change.reserve
        if not (in_hook or in_cave):
            raise ExternalToolError(
                f"C injection wrote outside hook/cave at target offset 0x{offset:X}"
            )
    setter(patched)

    return CInjectionRunResult(
        target=change.target,
        executable=executable,
        version=probe_armips_version(executable),
        symbol_bytes=None,
        symbol_destination=None,
        hook_address=hook_symbol.address,
        cave_address=cave_address,
        code_address=code_address,
        reserve=change.reserve,
        payload_size=len(compile_result.binary),
        thumb_interworking=compile_result.thumb_interworking,
        clang=compile_result.clang,
        clang_version=compile_result.clang_version,
        ld_lld=compile_result.ld_lld,
        lld_version=compile_result.lld_version,
        llvm_objcopy=compile_result.llvm_objcopy,
        objcopy_version=compile_result.objcopy_version,
    )
