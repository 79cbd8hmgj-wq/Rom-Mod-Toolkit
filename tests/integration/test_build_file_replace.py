import pytest

from rommod.errors import TargetNotFoundError
from rommod.platforms.nds.filesystem import extract_files, replace_file
from rommod.platforms.nds.rom import NdsRom


def test_replace_existing_file_roundtrip(synthetic_rom_path, tmp_path):
    rom = NdsRom.load(synthetic_rom_path)
    replace_file(rom, "/data/example.bin", b"changed")
    rebuilt = NdsRom.from_bytes(rom.serialize())
    destination = tmp_path / "extract"
    extract_files(rebuilt, destination)
    assert (destination / "data/example.bin").read_bytes() == b"changed"


def test_replace_missing_file_fails(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    with pytest.raises(TargetNotFoundError):
        replace_file(rom, "data/missing.bin", b"x")
