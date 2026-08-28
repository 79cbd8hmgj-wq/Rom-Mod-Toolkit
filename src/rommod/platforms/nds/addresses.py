"""Typed CPU-address and raw-file-offset mapping for NDS targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ndspy import codeCompression

from rommod.errors import AddressResolutionError
from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.overlays import get_overlay_raw, list_overlays
from rommod.platforms.nds.rom import NdsRom


@dataclass(frozen=True, order=True)
class CpuAddress:
    value: int


@dataclass(frozen=True, order=True)
class FileOffset:
    value: int


@dataclass(frozen=True)
class AddressRegion:
    target: str
    ram_address: CpuAddress
    file_size: int


def cpu_to_file_offset(region: AddressRegion, address: CpuAddress) -> FileOffset:
    delta = address.value - region.ram_address.value
    if delta < 0 or delta >= region.file_size:
        raise AddressResolutionError(
            f"CPU address 0x{address.value:08X} is outside {region.target}"
        )
    return FileOffset(delta)


def file_offset_to_cpu(region: AddressRegion, offset: FileOffset) -> CpuAddress:
    if offset.value < 0 or offset.value >= region.file_size:
        raise AddressResolutionError(
            f"file offset 0x{offset.value:X} is outside {region.target}"
        )
    return CpuAddress(region.ram_address.value + offset.value)


def _is_code_compressed(raw: bytes) -> bool:
    try:
        return codeCompression.decompress(raw) != raw
    except (ValueError, IndexError) as exc:
        raise AddressResolutionError(
            "Could not determine NDS code-compression state safely"
        ) from exc


def region_for_main(rom: NdsRom, processor: Literal["arm9", "arm7"]) -> AddressRegion:
    raw = get_main_binary(rom, processor)
    if _is_code_compressed(raw):
        raise AddressResolutionError(
            f"{processor} is compressed; raw file offsets cannot be mapped safely to CPU addresses"
        )
    ram_address = rom._nds.arm9RamAddress if processor == "arm9" else rom._nds.arm7RamAddress
    return AddressRegion(processor, CpuAddress(ram_address), len(raw))


def region_for_overlay(
    rom: NdsRom,
    processor: Literal["arm9", "arm7"],
    overlay_id: int,
) -> AddressRegion:
    infos = {info.overlay_id: info for info in list_overlays(rom, processor)}
    try:
        info = infos[overlay_id]
    except KeyError as exc:
        raise AddressResolutionError(f"Overlay not found: {processor}:{overlay_id}") from exc
    if info.compressed:
        raise AddressResolutionError(
            f"{processor} overlay {overlay_id} is compressed; raw file offsets cannot be mapped safely"
        )
    raw = get_overlay_raw(rom, processor, overlay_id)
    prefix = "overlay9" if processor == "arm9" else "overlay7"
    return AddressRegion(f"{prefix}:{overlay_id}", CpuAddress(info.ram_address), len(raw))
