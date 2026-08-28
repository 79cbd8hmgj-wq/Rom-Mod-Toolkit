"""NDS overlay metadata and raw target access."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rommod.errors import RomValidationError, TargetNotFoundError
from rommod.platforms.nds.rom import NdsRom

OverlayProcessor = Literal["arm9", "arm7"]


@dataclass(frozen=True)
class NdsOverlayInfo:
    processor: OverlayProcessor
    overlay_id: int
    ram_address: int
    ram_size: int
    bss_size: int
    static_init_start: int
    static_init_end: int
    file_id: int
    compressed_size: int
    flags: int
    compressed: bool


def _load(rom: NdsRom, processor: OverlayProcessor):
    try:
        if processor == "arm9":
            return rom._nds.loadArm9Overlays()
        if processor == "arm7":
            return rom._nds.loadArm7Overlays()
    except (ValueError, IndexError) as exc:
        raise RomValidationError(f"Could not parse {processor} overlay table: {exc}") from exc
    raise TargetNotFoundError(f"Unknown overlay processor: {processor}")


def list_overlays(rom: NdsRom, processor: OverlayProcessor) -> tuple[NdsOverlayInfo, ...]:
    overlays = _load(rom, processor)
    return tuple(
        NdsOverlayInfo(
            processor=processor,
            overlay_id=overlay_id,
            ram_address=overlay.ramAddress,
            ram_size=overlay.ramSize,
            bss_size=overlay.bssSize,
            static_init_start=overlay.staticInitStart,
            static_init_end=overlay.staticInitEnd,
            file_id=overlay.fileID,
            compressed_size=overlay.compressedSize,
            flags=overlay.flags,
            compressed=overlay.compressed,
        )
        for overlay_id, overlay in sorted(overlays.items())
    )


def _find_info(rom: NdsRom, processor: OverlayProcessor, overlay_id: int) -> NdsOverlayInfo:
    for info in list_overlays(rom, processor):
        if info.overlay_id == overlay_id:
            return info
    raise TargetNotFoundError(f"Overlay not found: {processor}:{overlay_id}")


def get_overlay_raw(rom: NdsRom, processor: OverlayProcessor, overlay_id: int) -> bytes:
    info = _find_info(rom, processor, overlay_id)
    try:
        return bytes(rom._nds.files[info.file_id])
    except IndexError as exc:
        raise RomValidationError(
            f"Overlay {processor}:{overlay_id} references invalid file ID {info.file_id}"
        ) from exc


def set_overlay_raw(rom: NdsRom, processor: OverlayProcessor, overlay_id: int, data: bytes) -> None:
    info = _find_info(rom, processor, overlay_id)
    try:
        rom._nds.files[info.file_id] = bytes(data)
    except IndexError as exc:
        raise RomValidationError(
            f"Overlay {processor}:{overlay_id} references invalid file ID {info.file_id}"
        ) from exc
