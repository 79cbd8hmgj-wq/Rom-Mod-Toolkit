from __future__ import annotations

import struct

import pytest

from rommod.errors import RomValidationError
from rommod.platforms.nds.validation import verify_project, verify_rom
from rommod.projects.build import build_project
from rommod.projects.project import init_project


def test_verify_rom_reports_valid_metadata(synthetic_rom_path):
    report = verify_rom(synthetic_rom_path)
    assert report.valid is True
    assert report.metadata.game_code == "TST1"
    assert "fat_entries" in report.checks
    assert "fresh_parse" in report.checks


def test_verify_rom_rejects_truncated_arm9_range(synthetic_rom_path, tmp_path):
    data = bytearray(synthetic_rom_path.read_bytes())
    struct.pack_into("<I", data, 0x2C, len(data))
    broken = tmp_path / "bad-arm9.nds"
    broken.write_bytes(data)
    with pytest.raises(RomValidationError, match="ARM9 range"):
        verify_rom(broken)


def test_verify_rom_rejects_misaligned_fat_size(synthetic_rom_path, tmp_path):
    data = bytearray(synthetic_rom_path.read_bytes())
    fat_size = struct.unpack_from("<I", data, 0x4C)[0]
    struct.pack_into("<I", data, 0x4C, fat_size - 1)
    broken = tmp_path / "bad-fat-size.nds"
    broken.write_bytes(data)
    with pytest.raises(RomValidationError, match="FAT size"):
        verify_rom(broken)


def test_verify_rom_rejects_invalid_fat_entry(synthetic_rom_path, tmp_path):
    data = bytearray(synthetic_rom_path.read_bytes())
    fat_offset = struct.unpack_from("<I", data, 0x48)[0]
    struct.pack_into("<II", data, fat_offset, len(data) + 4, len(data) + 8)
    broken = tmp_path / "bad-fat-entry.nds"
    broken.write_bytes(data)
    with pytest.raises(RomValidationError, match="FAT entry 0"):
        verify_rom(broken)


def test_verify_rom_rejects_overlay_file_id_outside_fat(synthetic_rom_path, tmp_path):
    data = bytearray(synthetic_rom_path.read_bytes())
    overlay_offset = struct.unpack_from("<I", data, 0x50)[0]
    assert overlay_offset != 0
    struct.pack_into("<I", data, overlay_offset + 0x18, 999)
    broken = tmp_path / "bad-overlay.nds"
    broken.write_bytes(data)
    with pytest.raises(RomValidationError, match="overlay 0.*file ID 999"):
        verify_rom(broken)


def test_verify_project_checks_configured_output(synthetic_rom_path, tmp_path):
    project = tmp_path / "mod"
    init_project(synthetic_rom_path, project)
    built = build_project(project)
    report = verify_project(project)
    assert report.valid is True
    assert report.metadata.sha256 == built.output_sha256


def test_verify_project_rejects_missing_output(synthetic_rom_path, tmp_path):
    project = tmp_path / "mod"
    init_project(synthetic_rom_path, project)
    with pytest.raises(RomValidationError, match="output.*missing"):
        verify_project(project)


def test_verify_cli_prints_report(synthetic_rom_path, capsys):
    from rommod.cli import main

    assert main(["verify", str(synthetic_rom_path)]) == 0
    captured = capsys.readouterr()
    assert '"valid": true' in captured.out
    assert '"game_code": "TST1"' in captured.out
