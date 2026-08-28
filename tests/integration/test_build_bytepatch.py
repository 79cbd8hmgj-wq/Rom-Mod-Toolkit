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


def test_build_project_applies_arm9_patch(synthetic_rom_path, tmp_path):
    from rommod.projects.build import build_project
    from rommod.projects.manifest import ProjectManifest, write_manifest
    from rommod.projects.project import init_project

    project = tmp_path / "patch-project"
    manifest = init_project(synthetic_rom_path, project)
    change = BytePatchChange("arm9", 4, bytes([5, 6]), b"\xFA\xFB")
    write_manifest(
        project,
        ProjectManifest(manifest.schema_version, manifest.platform, manifest.source, manifest.output, (change,)),
    )

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    assert get_main_binary(rebuilt, "arm9")[4:6] == b"\xFA\xFB"


def test_build_patch_mismatch_leaves_no_output(synthetic_rom_path, tmp_path):
    import pytest

    from rommod.errors import PatchMismatchError
    from rommod.projects.build import build_project
    from rommod.projects.manifest import ProjectManifest, write_manifest
    from rommod.projects.project import init_project

    project = tmp_path / "bad-patch"
    manifest = init_project(synthetic_rom_path, project)
    bad = BytePatchChange("arm9", 4, b"\x00\x00", b"\xFA\xFB")
    write_manifest(
        project,
        ProjectManifest(manifest.schema_version, manifest.platform, manifest.source, manifest.output, (bad,)),
    )
    output = project / manifest.output.rom

    with pytest.raises(PatchMismatchError):
        build_project(project)
    assert not output.exists()
