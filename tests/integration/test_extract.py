from rommod.platforms.nds.filesystem import extract_files, list_files
from rommod.platforms.nds.rom import NdsRom


def test_lists_named_nitrofs_file(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    entries = list_files(rom)
    assert [(e.path, e.file_id, e.size) for e in entries] == [("data/example.bin", 0, 13)]


def test_extracts_named_nitrofs_file(synthetic_rom_path, tmp_path):
    rom = NdsRom.load(synthetic_rom_path)
    destination = tmp_path / "extract"
    written = extract_files(rom, destination)
    assert destination / "data/example.bin" in written
    assert (destination / "data/example.bin").read_bytes() == b"original-data"
