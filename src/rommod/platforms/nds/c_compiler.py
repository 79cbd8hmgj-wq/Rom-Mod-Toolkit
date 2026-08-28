"""Freestanding ARM C payload compilation for NDS injection."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

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


def _require_success(result, stage: str) -> None:
    if result.returncode == 0:
        return
    diagnostics = (result.stdout + "\n" + result.stderr).strip()
    raise ExternalToolError(
        f"{stage} failed with exit code {result.returncode}: {diagnostics}"
    )


def _validated_link_symbol_lines(link_symbols: dict[str, int] | None) -> str:
    if not link_symbols:
        return ""
    lines: list[str] = []
    seen: set[str] = set()
    for name, address in link_symbols.items():
        if not isinstance(name, str) or not _LINK_SYMBOL.fullmatch(name):
            raise BuildError(f"C link symbol name {name!r} is not a safe identifier")
        if name == "rommod_payload":
            raise BuildError("C link symbol 'rommod_payload' is reserved by the toolkit")
        lowered = name.lower()
        if lowered in seen:
            raise BuildError(f"duplicate C link symbol name {name!r}")
        seen.add(lowered)
        if not isinstance(address, int) or isinstance(address, bool) or not 0 <= address <= 0xFFFFFFFF:
            raise BuildError(f"C link symbol {name!r} must use a 32-bit non-negative address")
        lines.append(f"{name} = 0x{address:08X};")
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


def compile_arm_c_payload(
    project_dir: Path,
    source: str,
    *,
    load_address: int,
    capacity: int,
    tools: ToolsConfig,
    job_index: int,
    link_symbols: dict[str, int] | None = None,
) -> CCompileResult:
    project = Path(project_dir).resolve()
    if load_address < 0 or load_address > 0xFFFFFFFF or load_address % 4:
        raise BuildError("C payload load address must be a 4-byte-aligned 32-bit address")
    if capacity <= 0:
        raise BuildError("C payload capacity must be positive")

    source_path = resolve_inside(project, source)
    if not source_path.is_file():
        raise BuildError(f"C payload source does not exist: {source}")

    clang = resolve_clang(project, tools.clang)
    ld_lld = resolve_ld_lld(project, tools.ld_lld)
    llvm_objcopy = resolve_llvm_objcopy(project, tools.llvm_objcopy)

    work_root = resolve_inside(project, "build/work/c")
    job_dir = work_root / f"{job_index:04d}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)

    object_path = job_dir / "payload.o"
    elf_path = job_dir / "payload.elf"
    binary_path = job_dir / "payload.bin"
    linker_path = job_dir / "payload.ld"
    linker_path.write_text(_linker_script(load_address, link_symbols), encoding="utf-8")

    compile_result = run_capture(
        [
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
            "-c",
            source_path,
            "-o",
            object_path,
        ],
        cwd=job_dir,
    )
    _require_success(compile_result, "clang C compilation")

    link_result = run_capture(
        [
            ld_lld,
            "--fatal-warnings",
            "-T",
            linker_path,
            object_path,
            "-o",
            elf_path,
        ],
        cwd=job_dir,
    )
    _require_success(link_result, "LLD C payload link")

    objcopy_result = run_capture(
        [
            llvm_objcopy,
            "-O",
            "binary",
            "--only-section=.text",
            elf_path,
            binary_path,
        ],
        cwd=job_dir,
    )
    _require_success(objcopy_result, "llvm-objcopy C payload extraction")

    if not binary_path.is_file():
        raise ExternalToolError("llvm-objcopy completed without producing payload.bin")
    binary = binary_path.read_bytes()
    if not binary:
        raise ExternalToolError("compiled C payload is empty")
    if len(binary) > capacity:
        raise BuildError(
            f"compiled C payload is {len(binary)} bytes but only {capacity} bytes are available"
        )

    return CCompileResult(
        binary=binary,
        load_address=load_address,
        clang=clang,
        ld_lld=ld_lld,
        llvm_objcopy=llvm_objcopy,
        clang_version=probe_version(clang, "--version"),
        lld_version=probe_version(ld_lld, "--version"),
        objcopy_version=probe_version(llvm_objcopy, "--version"),
    )
