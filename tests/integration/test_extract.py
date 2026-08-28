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


def test_extract_project_exports_binaries_overlays_and_metadata(synthetic_rom_path, tmp_path):
    from rommod.platforms.nds.extract import extract_project
    from rommod.projects.project import init_project

    project = tmp_path / "mod"
    init_project(synthetic_rom_path, project)
    report = extract_project(project)

    assert report["platform"] == "nds"
    assert (project / "build/extracted/arm9.bin").read_bytes() == bytes(range(1, 65))
    assert (project / "build/extracted/arm7.bin").read_bytes() == bytes(range(65, 97))
    assert (project / "build/extracted/overlays/arm9/0.bin").read_bytes() == bytes(range(0xA0, 0xB0))
    assert (project / "build/extracted/overlays/arm9/index.json").is_file()
    assert (project / "build/extracted/metadata.json").is_file()
    assert (project / "reports/source.json").is_file()
