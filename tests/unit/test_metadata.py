from rommod.platforms.nds.rom import NdsRom


def test_load_metadata(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    meta = rom.metadata()
    assert meta.title == "ROMMOD TEST"
    assert meta.game_code == "TST1"
    assert meta.maker_code == "RM"
    assert meta.arm9_size == 64
    assert meta.arm7_size == 32
    assert meta.arm9_ram_address == 0x02000000
