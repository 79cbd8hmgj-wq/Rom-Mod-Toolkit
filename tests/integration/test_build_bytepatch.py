from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.bytepatch import apply_byte_change
from rommod.platforms.nds.overlays import get_overlay_raw
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.manifest import BytePatchChange


def test_arm9_byte_change_roundtrip(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    change = BytePatchChange("arm9", 4, bytes([5, 6]), b"\xFA\xFB")
    apply_byte_change(rom, change)
    rebuilt = NdsRom.from_bytes(rom.serialize())
    assert get_main_binary(rebuilt, "arm9")[4:6] == b"\xFA\xFB"


def test_overlay_byte_change_roundtrip(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    change = BytePatchChange("overlay9:0", 2, b"\xA2\xA3", b"\x11\x22")
    apply_byte_change(rom, change)
    rebuilt = NdsRom.from_bytes(rom.serialize())
    assert get_overlay_raw(rebuilt, "arm9", 0)[2:4] == b"\x11\x22"


def test_nitrofs_byte_change_roundtrip(synthetic_rom_path, tmp_path):
    from rommod.platforms.nds.filesystem import extract_files

    rom = NdsRom.load(synthetic_rom_path)
    change = BytePatchChange("file:data/example.bin", 0, b"orig", b"EDIT")
    apply_byte_change(rom, change)
    rebuilt = NdsRom.from_bytes(rom.serialize())
    extract_files(rebuilt, tmp_path / "files")
    assert (tmp_path / "files/data/example.bin").read_bytes().startswith(b"EDIT")
