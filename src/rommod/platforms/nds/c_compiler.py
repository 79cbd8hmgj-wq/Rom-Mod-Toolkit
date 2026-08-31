"""Freestanding ARM C payload compilation for NDS injection."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from rommod.core.paths import resolve_inside
from rommod.core.subprocesses import (
    probe_version,
    resolve_clang,
    resolve_ld_lld,
    resolve_llvm_objcopy,
    run_capture,
)
from rommod.errors import BuildError, ExternalToolError
from rommod.projects.manifest import ToolsConfig


_LINK_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_C_DEFINE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class CCompileResult:
    binary: bytes
    load_address: int
    clang: Path
    ld_lld: Path
    llvm_objcopy: Path
    clang_version: str
    lld_version: str
    objcopy_version: str
    thumb_interworking: bool = False


def _require_success(result, stage: str) -> None:
    if result.returncode == 0:
        return
    diagnostics = (result.stdout + "\n" + result.stderr).strip()
    raise ExternalToolError(f"{stage} failed with exit code {result.returncode}: {diagnostics}")


def _validate_link_symbol(name: str, address: int, *, kind: str) -> None:
    if not isinstance(name, str) or not _LINK_SYMBOL.fullmatch(name):
        raise BuildError(f"C {kind} symbol name {name!r} is not a safe identifier")
    if name == "rommod_payload":
        raise BuildError("C link symbol 'rommod_payload' is reserved by the toolkit")
    if not isinstance(address, int) or isinstance(address, bool) or not 0 <= address <= 0xFFFFFFFF:
        raise BuildError(f"C {kind} symbol {name!r} must use a 32-bit non-negative address")


def _validated_link_symbol_lines(link_symbols: dict[str, int] | None) -> str:
    if not link_symbols:
        return ""
    lines: list[str] = []
    seen: set[str] = set()
    for name, address in link_symbols.items():
        _validate_link_symbol(name, address, kind="link")
        lowered = name.lower()
        if lowered in seen:
            raise BuildError(f"duplicate C link symbol name {name!r}")
        seen.add(lowered)
        lines.append(f"{name} = 0x{address:08X};")
    return "\n".join(lines) + "\n"


def _thumb_veneer_source(thumb_link_symbols: dict[str, int] | None) -> str:
    if not thumb_link_symbols:
        return ""
    lines = [".syntax unified", ".arm"]
    seen: set[str] = set()
    for name, address in thumb_link_symbols.items():
        _validate_link_symbol(name, address, kind="Thumb")
        lowered = name.lower()
        if lowered in seen:
            raise BuildError(f"duplicate C Thumb symbol name {name!r}")
        seen.add(lowered)
        lines.extend([
            f'.section .text.__rommod_thumb_{name},"ax",%progbits',
            f".global {name}",
            f".type {name},%function",
            f"{name}:",
            "  ldr r12, [pc, #0]",
            "  bx r12",
            f"  .word 0x{(address | 1):08X}",
        ])
    return "\n".join(lines) + "\n"


def _linker_script(load_address: int, link_symbols: dict[str, int] | None = None) -> str:
    symbol_lines = _validated_link_symbol_lines(link_symbols)
    return symbol_lines + f"""ENTRY(rommod_payload)
SECTIONS
{{
  . = 0x{load_address:08X};
  .text : ALIGN(4)
  {{
    KEEP(*(.text.rommod_payload))
    *(.text*)
    *(.rodata*)
  }}
  .data : {{ *(.data*) }}
  .bss : {{ *(.bss*) *(COMMON) }}
  /DISCARD/ : {{ *(.ARM.exidx*) *(.comment*) *(.note*) }}
}}
ASSERT(DEFINED(rommod_payload), "rommod_payload entry function is required")
ASSERT(SIZEOF(.data) == 0, "writable data is not supported")
ASSERT(SIZEOF(.bss) == 0, "bss is not supported")
"""


def _normalize_sources(source: str | None, sources: Sequence[str] | None) -> tuple[str, ...]:
    if source is not None and sources:
        raise BuildError("C payload must provide source or sources, not both")
    if source is not None:
        if not isinstance(source, str) or not source:
            raise BuildError("C payload source must be a non-empty string")
        return (source,)
    if not sources:
        raise BuildError("C payload must provide at least one source file")
    normalized: list[str] = []
    for index, value in enumerate(sources):
        if not isinstance(value, str) or not value:
            raise BuildError(f"C payload sources[{index}] must be a non-empty string")
        normalized.append(value)
    return tuple(normalized)


def _resolve_include_dirs(project: Path, include_dirs: Sequence[str] | None) -> tuple[Path, ...]:
    if not include_dirs:
        return ()
    resolved: list[Path] = []
    for index, value in enumerate(include_dirs):
        if not isinstance(value, str) or not value:
            raise BuildError(f"C include_dirs[{index}] must be a non-empty string")
        path = resolve_inside(project, value)
        if not path.is_dir():
            raise BuildError(f"C include directory does not exist or is not a directory: {value}")
        resolved.append(path)
    return tuple(resolved)


def _normalize_defines(defines: Sequence[str] | None) -> tuple[str, ...]:
    if not defines:
        return ()
    normalized: list[str] = []
    for index, value in enumerate(defines):
        if not isinstance(value, str) or not value:
            raise BuildError(f"C define[{index}] must be a non-empty string")
        if any(ch in value for ch in "\r\n\0"):
            raise BuildError(f"C define[{index}] must not contain control characters")
        name = value.split("=", 1)[0]
        if not _C_DEFINE_NAME.fullmatch(name):
            raise BuildError(f"C define[{index}] has invalid macro name {name!r}")
        normalized.append(value)
    return tuple(normalized)


def compile_arm_c_payload(
    project_dir: Path,
    source: str | None,
    *,
    load_address: int,
    capacity: int,
    tools: ToolsConfig,
    job_index: int,
    sources: Sequence[str] | None = None,
    include_dirs: Sequence[str] | None = None,
    defines: Sequence[str] | None = None,
    link_symbols: dict[str, int] | None = None,
    thumb_link_symbols: dict[str, int] | None = None,
) -> CCompileResult:
    project = Path(project_dir).resolve()
    if load_address < 0 or load_address > 0xFFFFFFFF or load_address % 4:
        raise BuildError("C payload load address must be a 4-byte-aligned 32-bit address")
    if capacity <= 0:
        raise BuildError("C payload capacity must be positive")

    direct_names = {name.lower() for name in (link_symbols or {})}
    thumb_names = {name.lower() for name in (thumb_link_symbols or {})}
    overlap = direct_names & thumb_names
    if overlap:
        raise BuildError(f"C symbol cannot be both direct and Thumb-interworked: {sorted(overlap)[0]}")

    source_names = _normalize_sources(source, sources)
    source_paths: list[Path] = []
    for name in source_names:
        source_path = resolve_inside(project, name)
        if not source_path.is_file():
            raise BuildError(f"C payload source does not exist: {name}")
        source_paths.append(source_path)

    include_paths = _resolve_include_dirs(project, include_dirs)
    include_args: list[str | Path] = []
    for include_path in include_paths:
        include_args.extend(["-I", include_path])
    define_args = [f"-D{value}" for value in _normalize_defines(defines)]

    clang = resolve_clang(project, tools.clang)
    ld_lld = resolve_ld_lld(project, tools.ld_lld)
    llvm_objcopy = resolve_llvm_objcopy(project, tools.llvm_objcopy)

    work_root = resolve_inside(project, "build/work/c")
    job_dir = work_root / f"{job_index:04d}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    veneer_source_path = job_dir / "thumb_veneers.s"
    veneer_object_path = job_dir / "thumb_veneers.o"
    elf_path = job_dir / "payload.elf"
    binary_path = job_dir / "payload.bin"
    linker_path = job_dir / "payload.ld"
    linker_path.write_text(_linker_script(load_address, link_symbols), encoding="utf-8")

    link_objects: list[Path] = []
    for index, source_path in enumerate(source_paths):
        object_path = job_dir / f"payload_{index:03d}.o"
        compile_result = run_capture([
            clang,
            "--target=arm-none-eabi",
            "-mcpu=arm946e-s",
            "-marm",
            "-Oz",
            "-ffreestanding",
            "-fno-builtin",
            "-fno-stack-protector",
            "-fno-unwind-tables",
            "-fno-asynchronous-unwind-tables",
            "-fno-pic",
            "-fno-pie",
            "-ffunction-sections",
            "-fdata-sections",
            "-fno-common",
            "-nostdlib",
            *include_args,
            *define_args,
            "-c",
            source_path,
            "-o",
            object_path,
        ], cwd=job_dir)
        _require_success(compile_result, f"clang C compilation ({source_names[index]})")
        link_objects.append(object_path)

    veneer_source = _thumb_veneer_source(thumb_link_symbols)
    if veneer_source:
        veneer_source_path.write_text(veneer_source, encoding="utf-8")
        veneer_result = run_capture([
            clang,
            "--target=arm-none-eabi",
            "-mcpu=arm946e-s",
            "-marm",
            "-c",
            veneer_source_path,
            "-o",
            veneer_object_path,
        ], cwd=job_dir)
        _require_success(veneer_result, "clang Thumb veneer assembly")
        link_objects.append(veneer_object_path)

    link_result = run_capture([
        ld_lld,
        "--fatal-warnings",
        "--gc-sections",
        "-T",
        linker_path,
        *link_objects,
        "-o",
        elf_path,
    ], cwd=job_dir)
    _require_success(link_result, "LLD C payload link")

    objcopy_result = run_capture([
        llvm_objcopy,
        "-O",
        "binary",
        "--only-section=.text",
        elf_path,
        binary_path,
    ], cwd=job_dir)
    _require_success(objcopy_result, "llvm-objcopy C payload extraction")

    if not binary_path.is_file():
        raise ExternalToolError("llvm-objcopy completed without producing payload.bin")
    binary = binary_path.read_bytes()
    if not binary:
        raise ExternalToolError("compiled C payload is empty")
    if len(binary) > capacity:
        raise BuildError(f"compiled C payload is {len(binary)} bytes but only {capacity} bytes are available")

    return CCompileResult(
        binary=binary,
        load_address=load_address,
        clang=clang,
        ld_lld=ld_lld,
        llvm_objcopy=llvm_objcopy,
        clang_version=probe_version(clang, "--version"),
        lld_version=probe_version(ld_lld, "--version"),
        objcopy_version=probe_version(llvm_objcopy, "--version"),
        thumb_interworking=bool(thumb_link_symbols),
    )
