"""Read-only free-space discovery for NDS code targets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rommod.errors import BuildError
from rommod.platforms.nds.assembler import _target_state
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.manifest import load_manifest
from rommod.projects.project import verify_source


@dataclass(frozen=True)
class FreeSpaceCandidate:
    offset: int
    address: int
    size: int
    fill: int
    trailing: bool


@dataclass(frozen=True)
class FreeSpaceReport:
    target: str
    ram_address: int
    target_size: int
    min_size: int
    fill: int
    alignment: int
    candidates: tuple[FreeSpaceCandidate, ...]


def _validate_scan_config(
    *,
    min_size: int,
    fill: int,
    alignment: int,
    base_address: int,
    data_size: int,
) -> None:
    if not isinstance(min_size, int) or isinstance(min_size, bool) or min_size <= 0:
        raise BuildError("free-space minimum size must be positive")
    if not isinstance(alignment, int) or isinstance(alignment, bool) or alignment <= 0:
        raise BuildError("free-space alignment must be positive")
    if not isinstance(fill, int) or isinstance(fill, bool) or not 0 <= fill <= 0xFF:
        raise BuildError("free-space fill must be a byte")
    if (
        not isinstance(base_address, int)
        or isinstance(base_address, bool)
        or not 0 <= base_address <= 0xFFFFFFFF
    ):
        raise BuildError("free-space base address must be a 32-bit non-negative integer")
    if data_size and base_address + data_size - 1 > 0xFFFFFFFF:
        raise BuildError("free-space target extends beyond the 32-bit address space")


def scan_fill_runs(
    data: bytes,
    *,
    min_size: int,
    fill: int = 0,
    alignment: int = 4,
    base_address: int = 0,
) -> tuple[FreeSpaceCandidate, ...]:
    """Return aligned fill-run candidates without claiming they are executable-safe."""

    raw = bytes(data)
    _validate_scan_config(
        min_size=min_size,
        fill=fill,
        alignment=alignment,
        base_address=base_address,
        data_size=len(raw),
    )

    candidates: list[FreeSpaceCandidate] = []
    cursor = 0
    while cursor < len(raw):
        if raw[cursor] != fill:
            cursor += 1
            continue

        run_start = cursor
        while cursor < len(raw) and raw[cursor] == fill:
            cursor += 1
        run_end = cursor

        run_address = base_address + run_start
        aligned_address = ((run_address + alignment - 1) // alignment) * alignment
        aligned_start = aligned_address - base_address
        usable_size = run_end - aligned_start
        if usable_size < min_size:
            continue

        candidates.append(
            FreeSpaceCandidate(
                offset=aligned_start,
                address=aligned_address,
                size=usable_size,
                fill=fill,
                trailing=run_end == len(raw),
            )
        )

    return tuple(candidates)


def discover_project_caves(
    project_dir: Path,
    target: str,
    *,
    min_size: int,
    fill: int = 0,
    alignment: int = 4,
) -> FreeSpaceReport:
    """Scan one source-locked NDS code target and report fill-run candidates."""

    project = Path(project_dir).resolve()
    manifest = load_manifest(project)
    source = verify_source(project, manifest)
    rom = NdsRom.load(source)

    _architecture, region, data, _setter = _target_state(rom, target)
    candidates = scan_fill_runs(
        data,
        min_size=min_size,
        fill=fill,
        alignment=alignment,
        base_address=region.ram_address.value,
    )
    return FreeSpaceReport(
        target=target,
        ram_address=region.ram_address.value,
        target_size=len(data),
        min_size=min_size,
        fill=fill,
        alignment=alignment,
        candidates=candidates,
    )
