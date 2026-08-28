from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.overlays import get_overlay_raw, list_overlays
from rommod.platforms.nds.rom import NdsRom


def test_main_binary_access(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    assert get_main_binary(rom, "arm9") == bytes(range(1, 65))
    assert get_main_binary(rom, "arm7") == bytes(range(65, 97))


def test_overlay_metadata_and_raw_access(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    overlays = list_overlays(rom, "arm9")
    assert len(overlays) == 1
    assert overlays[0].overlay_id == 0
    assert overlays[0].ram_address == 0x02100000
    assert overlays[0].file_id == 1
    assert overlays[0].compressed is False
    assert get_overlay_raw(rom, "arm9", 0) == bytes(range(0xA0, 0xB0))
