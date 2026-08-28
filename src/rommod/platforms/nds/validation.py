"""NDS structural validation."""

from __future__ import annotations

import struct

from rommod.errors import RomValidationError


_HEADER_SIZE = 0x200


def _check_range(label: str, offset: int, size: int, total: int) -> None:
    if size == 0:
        return
    if offset < 0 or size < 0 or offset > total or size > total - offset:
        raise RomValidationError(
            f"{label} range is outside ROM: offset=0x{offset:X}, size=0x{size:X}, rom=0x{total:X}"
        )


def validate_nds_bytes(data: bytes) -> None:
    if len(data) < _HEADER_SIZE:
        raise RomValidationError(
            f"NDS image is too small for a header: 0x{len(data):X} < 0x{_HEADER_SIZE:X}"
        )
    try:
        arm9_offset, _, _, arm9_size = struct.unpack_from("<4I", data, 0x20)
        arm7_offset, _, _, arm7_size = struct.unpack_from("<4I", data, 0x30)
        (
            fnt_offset,
            fnt_size,
            fat_offset,
            fat_size,
            arm9_ov_offset,
            arm9_ov_size,
            arm7_ov_offset,
            arm7_ov_size,
        ) = struct.unpack_from("<8I", data, 0x40)
    except struct.error as exc:
        raise RomValidationError("NDS header fields could not be read") from exc

    total = len(data)
    _check_range("ARM9", arm9_offset, arm9_size, total)
    _check_range("ARM7", arm7_offset, arm7_size, total)
    _check_range("FNT", fnt_offset, fnt_size, total)
    _check_range("FAT", fat_offset, fat_size, total)
    _check_range("ARM9 overlay table", arm9_ov_offset, arm9_ov_size, total)
    _check_range("ARM7 overlay table", arm7_ov_offset, arm7_ov_size, total)
