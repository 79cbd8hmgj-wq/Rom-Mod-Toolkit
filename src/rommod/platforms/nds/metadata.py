"""Normalized NDS metadata."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NdsMetadata:
    title: str
    game_code: str
    maker_code: str
    rom_version: int
    arm9_rom_offset: int
    arm9_entry_address: int
    arm9_ram_address: int
    arm9_size: int
    arm7_rom_offset: int
    arm7_entry_address: int
    arm7_ram_address: int
    arm7_size: int
    fnt_offset: int
    fnt_size: int
    fat_offset: int
    fat_size: int
    arm9_overlay_offset: int
    arm9_overlay_size: int
    arm7_overlay_offset: int
    arm7_overlay_size: int
    banner_offset: int
    source_size: int
    sha256: str
