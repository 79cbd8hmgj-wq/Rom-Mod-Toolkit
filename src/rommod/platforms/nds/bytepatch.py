"""Guarded exact byte patches for serialized NDS targets."""

from __future__ import annotations

from rommod.errors import PatchMismatchError, TargetNotFoundError
from rommod.platforms.nds.binaries import get_main_binary, set_main_binary
from rommod.platforms.nds.filesystem import replace_file
from rommod.platforms.nds.overlays import get_overlay_raw, set_overlay_raw
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.manifest import BytePatchChange


def apply_guarded_patch(data: bytes, offset: int, expected: bytes, replacement: bytes) -> bytes:
    if len(expected) != len(replacement):
        raise PatchMismatchError("expected and replacement byte sequences must be the same length")
    if offset < 0 or offset + len(expected) > len(data):
        raise PatchMismatchError(
            f"patch range 0x{offset:X}..0x{offset + len(expected):X} is outside target size 0x{len(data):X}"
        )
    actual = data[offset : offset + len(expected)]
    if actual != expected:
        raise PatchMismatchError(
            f"expected bytes {expected.hex(' ').upper()} at 0x{offset:X}, "
            f"found {actual.hex(' ').upper()}"
        )
    out = bytearray(data)
    out[offset : offset + len(expected)] = replacement
    return bytes(out)


def _parse_overlay_target(target: str, prefix: str) -> int:
    raw_id = target[len(prefix) :]
    if not raw_id or not raw_id.isdecimal():
        raise TargetNotFoundError(f"Invalid overlay target: {target}")
    return int(raw_id, 10)


def _normalize_file_target(target: str) -> str:
    path = target[len("file:") :].replace("\\", "/").strip("/")
    if not path:
        raise TargetNotFoundError("NitroFS byte-patch target is empty")
    return path


def apply_byte_change(rom: NdsRom, change: BytePatchChange) -> None:
    target = change.target
    if target in ("arm9", "arm7"):
        original = get_main_binary(rom, target)
        patched = apply_guarded_patch(original, change.offset, change.expected, change.replacement)
        set_main_binary(rom, target, patched)
        return

    if target.startswith("overlay9:"):
        overlay_id = _parse_overlay_target(target, "overlay9:")
        original = get_overlay_raw(rom, "arm9", overlay_id)
        patched = apply_guarded_patch(original, change.offset, change.expected, change.replacement)
        set_overlay_raw(rom, "arm9", overlay_id, patched)
        return

    if target.startswith("overlay7:"):
        overlay_id = _parse_overlay_target(target, "overlay7:")
        original = get_overlay_raw(rom, "arm7", overlay_id)
        patched = apply_guarded_patch(original, change.offset, change.expected, change.replacement)
        set_overlay_raw(rom, "arm7", overlay_id, patched)
        return

    if target.startswith("file:"):
        path = _normalize_file_target(target)
        try:
            original = bytes(rom._nds.getFileByName(path))
        except ValueError as exc:
            raise TargetNotFoundError(f"NitroFS file not found: {path}") from exc
        patched = apply_guarded_patch(original, change.offset, change.expected, change.replacement)
        replace_file(rom, path, patched)
        return

    raise TargetNotFoundError(f"Unknown byte-patch target: {target}")
