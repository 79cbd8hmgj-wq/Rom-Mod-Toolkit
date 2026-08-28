from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from rommod.errors import ExternalToolError
from rommod.platforms.nds.binaries import get_main_binary
from rommod.platforms.nds.overlays import get_overlay_raw
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.build import build_project
from rommod.projects.manifest import ArmipsChange, ToolsConfig, write_manifest
from rommod.projects.project import init_project


def _real_armips() -> str:
    path = os.environ.get("ROMMOD_ARMIPS") or shutil.which("armips")
    if not path:
        pytest.skip("real armips executable not available")
    return str(Path(path).resolve())


@pytest.mark.parametrize(
    ("target", "address", "reader", "offset"),
    [
        ("arm9", 0x02000004, lambda rom: get_main_binary(rom, "arm9"), 4),
        ("arm7", 0x02380004, lambda rom: get_main_binary(rom, "arm7"), 4),
        ("overlay9:0", 0x02100004, lambda rom: get_overlay_raw(rom, "arm9", 0), 4),
    ],
)
def test_build_applies_real_armips_patch_and_symbols(
    synthetic_rom_path: Path,
    tmp_path: Path,
    target: str,
    address: int,
    reader,
    offset: int,
):
    armips = _real_armips()
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    script = project / "asm/patch.asm"
    script.write_text(
        f".org 0x{address:08X}\n.word 0x11223344\nPatchLabel:\n",
        encoding="utf-8",
    )
    manifest = replace(
        manifest,
        changes=(ArmipsChange(target=target, script="asm/patch.asm", symbols="reports/patch.sym"),),
        tools=ToolsConfig(armips=armips),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    assert reader(rebuilt)[offset : offset + 4] == bytes.fromhex("44 33 22 11")
    assert "patchlabel" in (project / "reports/patch.sym").read_text(encoding="utf-8").lower()
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["changes"][0]["type"] == "armips"
    assert "armips" in report["tools"]
    assert "0.11.0" in report["tools"]["armips"]["version"]


def test_missing_armips_does_not_write_output(synthetic_rom_path: Path, tmp_path: Path, monkeypatch):
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    (project / "asm/patch.asm").write_text(".org 0x02000000\n.word 0\n", encoding="utf-8")
    manifest = replace(manifest, changes=(ArmipsChange(target="arm9", script="asm/patch.asm"),))
    write_manifest(project, manifest)
    monkeypatch.delenv("ROMMOD_ARMIPS", raising=False)
    monkeypatch.setenv("PATH", "")

    with pytest.raises(ExternalToolError, match="armips"):
        build_project(project)
    assert not (project / "build/output/synthetic-modded.nds").exists()


def test_build_uses_component_aware_imported_symbol(synthetic_rom_path: Path, tmp_path: Path):
    armips = _real_armips()
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(
        json.dumps(
            {
                "symbols": [
                    {
                        "component": "battle_overlay",
                        "address": 0x02100004,
                        "offset": 4,
                        "name": "PatchSite",
                        "kind": "function",
                        "instruction_set": "arm",
                        "confidence": "high",
                        "evidence": ["test"],
                    },
                    {
                        "component": "other_overlay",
                        "address": 0x02100004,
                        "offset": 4,
                        "name": "OtherPatchSite",
                        "kind": "function",
                        "instruction_set": "thumb",
                        "confidence": "high",
                        "evidence": ["test"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (project / "asm/patch.asm").write_text(
        ".org PatchSite\n.word 0xAABBCCDD\n",
        encoding="utf-8",
    )
    manifest = replace(
        manifest,
        changes=(
            ArmipsChange(
                target="overlay9:0",
                script="asm/patch.asm",
                symbol_file="analysis/symbols.json",
                symbol_component="battle_overlay",
            ),
        ),
        tools=ToolsConfig(armips=armips),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    assert get_overlay_raw(rebuilt, "arm9", 0)[4:8] == bytes.fromhex("DD CC BB AA")


def test_symbol_import_rejects_wrong_component_offset(synthetic_rom_path: Path, tmp_path: Path):
    armips = _real_armips()
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(
        json.dumps(
            [
                {
                    "component": "arm9",
                    "address": 0x02000008,
                    "offset": 4,
                    "name": "BadSite",
                    "kind": "function",
                    "instruction_set": "arm",
                    "confidence": "high",
                    "evidence": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (project / "asm/patch.asm").write_text(".org BadSite\n.word 0\n", encoding="utf-8")
    manifest = replace(
        manifest,
        changes=(
            ArmipsChange(
                target="arm9",
                script="asm/patch.asm",
                symbol_file="analysis/symbols.json",
            ),
        ),
        tools=ToolsConfig(armips=armips),
    )
    write_manifest(project, manifest)
    with pytest.raises(ExternalToolError, match="offset"):
        build_project(project)


@pytest.mark.parametrize(
    ("name", "records", "message"),
    [
        (
            "unsafe",
            [
                {
                    "component": "arm9",
                    "address": 0x02000004,
                    "offset": 4,
                    "name": "Bad Name",
                    "kind": "function",
                    "instruction_set": "arm",
                    "confidence": "high",
                    "evidence": [],
                }
            ],
            "identifier",
        ),
        (
            "duplicate",
            [
                {
                    "component": "arm9",
                    "address": 0x02000004,
                    "offset": 4,
                    "name": "SameName",
                    "kind": "function",
                    "instruction_set": "arm",
                    "confidence": "high",
                    "evidence": [],
                },
                {
                    "component": "arm9",
                    "address": 0x02000008,
                    "offset": 8,
                    "name": "SameName",
                    "kind": "label",
                    "instruction_set": "arm",
                    "confidence": "high",
                    "evidence": [],
                },
            ],
            "duplicate",
        ),
    ],
)
def test_symbol_import_rejects_unsafe_or_duplicate_names(
    synthetic_rom_path: Path,
    tmp_path: Path,
    name: str,
    records: list[dict],
    message: str,
):
    armips = _real_armips()
    project = tmp_path / f"mod-{name}"
    manifest = init_project(synthetic_rom_path, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(json.dumps(records), encoding="utf-8")
    (project / "asm/patch.asm").write_text(".org 0x02000000\n.word 0\n", encoding="utf-8")
    manifest = replace(
        manifest,
        changes=(
            ArmipsChange(target="arm9", script="asm/patch.asm", symbol_file="analysis/symbols.json"),
        ),
        tools=ToolsConfig(armips=armips),
    )
    write_manifest(project, manifest)
    with pytest.raises(ExternalToolError, match=message):
        build_project(project)
