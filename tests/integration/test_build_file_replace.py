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


def test_build_project_applies_file_replace_and_is_deterministic(synthetic_rom_path, tmp_path):
    import json

    from rommod.platforms.nds.filesystem import extract_files
    from rommod.projects.build import build_project
    from rommod.projects.manifest import FileReplaceChange, ProjectManifest, write_manifest
    from rommod.projects.project import init_project

    source_before = synthetic_rom_path.read_bytes()
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    replacement = project / "files/example.bin"
    replacement.write_bytes(b"replacement-data")
    write_manifest(
        project,
        ProjectManifest(
            manifest.schema_version,
            manifest.platform,
            manifest.source,
            manifest.output,
            (FileReplaceChange("data/example.bin", "files/example.bin"),),
        ),
    )

    first = build_project(project)
    first_bytes = first.output_path.read_bytes()
    second = build_project(project)

    assert first.output_sha256 == second.output_sha256
    assert first_bytes == second.output_path.read_bytes()
    assert synthetic_rom_path.read_bytes() == source_before
    rebuilt = NdsRom.load(second.output_path)
    extract_files(rebuilt, tmp_path / "rebuilt-files")
    assert (tmp_path / "rebuilt-files/data/example.bin").read_bytes() == b"replacement-data"

    report = json.loads(second.report_path.read_text(encoding="utf-8"))
    assert report["source_sha256"] == manifest.source.sha256
    assert report["output_sha256"] == second.output_sha256
    assert report["validation"] == {"declared_changes": True, "parse_reload": True}
    assert report["tools"]["ndspy"] == "4.2.0"


def test_build_applies_changes_in_manifest_order(synthetic_rom_path, tmp_path):
    from rommod.platforms.nds.filesystem import extract_files
    from rommod.projects.build import build_project
    from rommod.projects.manifest import BytePatchChange, FileReplaceChange, ProjectManifest, write_manifest
    from rommod.projects.project import init_project

    project = tmp_path / "ordered"
    manifest = init_project(synthetic_rom_path, project)
    (project / "files/example.bin").write_bytes(b"fresh-data")
    changes = (
        FileReplaceChange("data/example.bin", "files/example.bin"),
        BytePatchChange("file:data/example.bin", 0, b"fresh", b"FRESH"),
    )
    write_manifest(
        project,
        ProjectManifest(manifest.schema_version, manifest.platform, manifest.source, manifest.output, changes),
    )

    result = build_project(project)
    extract_files(NdsRom.load(result.output_path), tmp_path / "ordered-files")
    assert (tmp_path / "ordered-files/data/example.bin").read_bytes() == b"FRESH-data"
