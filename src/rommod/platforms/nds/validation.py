"""NDS structural validation and verification."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rommod.core.paths import resolve_inside
from rommod.errors import RomValidationError

if TYPE_CHECKING:
    from rommod.platforms.nds.metadata import NdsMetadata


_HEADER_SIZE = 0x200
_OVERLAY_RECORD_SIZE = 32
_FAT_RECORD_SIZE = 8


@dataclass(frozen=True)
class VerificationReport:
    valid: bool
    metadata: "NdsMetadata"
    checks: tuple[str, ...]


def _check_range(label: str, offset: int, size: int, total: int) -> None:
    if size == 0:
        return
    if offset < 0 or size < 0 or offset > total or size > total - offset:
        raise RomValidationError(
            f"{label} range is outside ROM: offset=0x{offset:X}, size=0x{size:X}, rom=0x{total:X}"
        )


def _header_regions(data: bytes) -> tuple[int, ...]:
    try:
        arm9_offset, _, _, arm9_size = struct.unpack_from("<4I", data, 0x20)
        arm7_offset, _, _, arm7_size = struct.unpack_from("<4I", data, 0x30)
        tables = struct.unpack_from("<8I", data, 0x40)
    except struct.error as exc:
        raise RomValidationError("NDS header fields could not be read") from exc
    return (arm9_offset, arm9_size, arm7_offset, arm7_size, *tables)


def _validate_fat(data: bytes, fat_offset: int, fat_size: int) -> int:
    if fat_size % _FAT_RECORD_SIZE:
        raise RomValidationError(
            f"FAT size must be divisible by {_FAT_RECORD_SIZE}, got 0x{fat_size:X}"
        )
    file_count = fat_size // _FAT_RECORD_SIZE
    total = len(data)
    for file_id in range(file_count):
        start, end = struct.unpack_from("<II", data, fat_offset + file_id * _FAT_RECORD_SIZE)
        if start > end or end > total:
            raise RomValidationError(
                f"FAT entry {file_id} is outside ROM or reversed: "
                f"start=0x{start:X}, end=0x{end:X}, rom=0x{total:X}"
            )
    return file_count


def _validate_overlay_table(
    data: bytes,
    label: str,
    offset: int,
    size: int,
    file_count: int,
) -> None:
    if size % _OVERLAY_RECORD_SIZE:
        raise RomValidationError(
            f"{label} overlay table size must be divisible by {_OVERLAY_RECORD_SIZE}, got 0x{size:X}"
        )
    for record_offset in range(0, size, _OVERLAY_RECORD_SIZE):
        overlay_id, = struct.unpack_from("<I", data, offset + record_offset)
        file_id, = struct.unpack_from("<I", data, offset + record_offset + 0x18)
        if file_id >= file_count:
            raise RomValidationError(
                f"{label} overlay {overlay_id} references file ID {file_id}, "
                f"but FAT contains {file_count} files"
            )


def validate_nds_bytes(data: bytes) -> None:
    if len(data) < _HEADER_SIZE:
        raise RomValidationError(
            f"NDS image is too small for a header: 0x{len(data):X} < 0x{_HEADER_SIZE:X}"
        )

    (
        arm9_offset,
        arm9_size,
        arm7_offset,
        arm7_size,
        fnt_offset,
        fnt_size,
        fat_offset,
        fat_size,
        arm9_ov_offset,
        arm9_ov_size,
        arm7_ov_offset,
        arm7_ov_size,
    ) = _header_regions(data)

    total = len(data)
    _check_range("ARM9", arm9_offset, arm9_size, total)
    _check_range("ARM7", arm7_offset, arm7_size, total)
    _check_range("FNT", fnt_offset, fnt_size, total)
    _check_range("FAT", fat_offset, fat_size, total)
    _check_range("ARM9 overlay table", arm9_ov_offset, arm9_ov_size, total)
    _check_range("ARM7 overlay table", arm7_ov_offset, arm7_ov_size, total)

    file_count = _validate_fat(data, fat_offset, fat_size)
    _validate_overlay_table(data, "ARM9", arm9_ov_offset, arm9_ov_size, file_count)
    _validate_overlay_table(data, "ARM7", arm7_ov_offset, arm7_ov_size, file_count)


def verify_rom(path: Path) -> VerificationReport:
    from rommod.platforms.nds.rom import NdsRom

    rom_path = Path(path)
    if not rom_path.is_file():
        raise RomValidationError(f"NDS ROM is missing: {rom_path}")
    data = rom_path.read_bytes()
    validate_nds_bytes(data)
    rom = NdsRom.from_bytes(data)
    return VerificationReport(
        valid=True,
        metadata=rom.metadata(),
        checks=(
            "header",
            "arm_ranges",
            "filesystem_ranges",
            "fat_entries",
            "overlay_tables",
            "fresh_parse",
        ),
    )


def verify_project(project_dir: Path) -> VerificationReport:
    from rommod.projects.manifest import load_manifest
    from rommod.projects.project import verify_source

    project = Path(project_dir).resolve()
    manifest = load_manifest(project)
    verify_source(project, manifest)
    output = resolve_inside(project, manifest.output.rom)
    if not output.is_file():
        raise RomValidationError(f"Configured project output is missing: {output}")
    return verify_rom(output)
