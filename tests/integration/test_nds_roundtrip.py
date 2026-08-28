from rommod.platforms.nds.rom import NdsRom


def test_untouched_save_reloads(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    rebuilt_bytes = rom.serialize()
    rebuilt = NdsRom.from_bytes(rebuilt_bytes)
    assert rebuilt.metadata().game_code == rom.metadata().game_code
    assert rebuilt.serialize() == rebuilt_bytes
