import pytest
from ndspy import codeCompression

from rommod.errors import AddressResolutionError
from rommod.platforms.nds.addresses import (
    AddressRegion,
    CpuAddress,
    FileOffset,
    cpu_to_file_offset,
    file_offset_to_cpu,
    region_for_main,
    region_for_overlay,
)
from rommod.platforms.nds.rom import NdsRom


def test_cpu_address_maps_to_file_offset():
    region = AddressRegion("arm9", CpuAddress(0x02000000), 0x100)
    assert cpu_to_file_offset(region, CpuAddress(0x02000020)) == FileOffset(0x20)


def test_file_offset_maps_to_cpu_address():
    region = AddressRegion("overlay9:3", CpuAddress(0x02100000), 0x80)
    assert file_offset_to_cpu(region, FileOffset(0x10)) == CpuAddress(0x02100010)


def test_cpu_address_outside_region_fails_closed():
    region = AddressRegion("arm7", CpuAddress(0x03800000), 0x40)
    with pytest.raises(AddressResolutionError):
        cpu_to_file_offset(region, CpuAddress(0x037FFFFC))


def test_main_and_overlay_regions_use_declared_ram_bases(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    assert region_for_main(rom, "arm9") == AddressRegion("arm9", CpuAddress(0x02000000), 64)
    assert region_for_overlay(rom, "arm9", 0) == AddressRegion(
        "overlay9:0", CpuAddress(0x02100000), 16
    )


def test_compressed_main_binary_rejects_raw_address_mapping(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    rom._nds.arm9 = codeCompression.compress(b"\0" * 64, False)
    with pytest.raises(AddressResolutionError, match="compressed"):
        region_for_main(rom, "arm9")
