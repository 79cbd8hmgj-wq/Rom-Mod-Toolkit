from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from rommod.errors import PatchMismatchError
from rommod.platforms.nds.binaries import get_main_binary, set_main_binary
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.build import build_project
from rommod.projects.manifest import InjectChange, ToolsConfig, write_manifest
from rommod.projects.project import init_project


def _real_armips() -> str:
    path = os.environ.get("ROMMOD_ARMIPS") or shutil.which("armips")
    if not path:
        pytest.skip("real armips executable not available")
    return str(Path(path).resolve())


def _source_with_arm9_cave(source: Path, output: Path) -> Path:
    rom = NdsRom.load(source)
    set_main_binary(rom, "arm9", get_main_binary(rom, "arm9") + b"\x00" * 64)
    output.write_bytes(rom.serialize())
    return output


def test_build_injects_arm_hook_into_trailing_cave(synthetic_rom_path: Path, tmp_path: Path):
    armips = _real_armips()
    source = _source_with_arm9_cave(synthetic_rom_path, tmp_path / "source.nds")
    project = tmp_path / "mod"
    manifest = init_project(source, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(
        json.dumps({"symbols": [{
            "component": "arm9",
            "address": 0x02000004,
            "offset": 4,
            "name": "HookSite",
            "kind": "function",
            "instruction_set": "arm",
            "confidence": "high",
            "evidence": ["test"],
        }]}), encoding="utf-8")
    (project / "asm/payload.asm").write_text("mov r0, #7\nPayloadLabel:\n", encoding="utf-8")
    manifest = replace(
        manifest,
        changes=(InjectChange(
            target="arm9",
            symbol_file="analysis/symbols.json",
            hook="HookSite",
            expected=bytes.fromhex("05 06 07 08"),
            script="asm/payload.asm",
            cave="auto",
            reserve=16,
            fill=0,
            symbols="reports/inject.sym",
        ),),
        tools=ToolsConfig(armips=armips),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")
    assert arm9[4:8] == bytes.fromhex("0D 00 00 EA")
    assert arm9[64:68] == bytes.fromhex("07 00 A0 E3")
    assert arm9[68:72] == bytes.fromhex("EF FF FF EA")
    assert "payloadlabel" in (project / "reports/inject.sym").read_text(encoding="utf-8").lower()
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["injections"][0]["hook_address"] == 0x02000004
    assert report["injections"][0]["cave_address"] == 0x02000040


def test_injection_expected_mismatch_does_not_write_output(synthetic_rom_path: Path, tmp_path: Path):
    armips = _real_armips()
    source = _source_with_arm9_cave(synthetic_rom_path, tmp_path / "source.nds")
    project = tmp_path / "mod"
    manifest = init_project(source, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(json.dumps([{
        "component": "arm9", "address": 0x02000004, "offset": 4, "name": "HookSite",
        "kind": "function", "instruction_set": "arm", "confidence": "high", "evidence": []
    }]), encoding="utf-8")
    (project / "asm/payload.asm").write_text("nop\n", encoding="utf-8")
    manifest = replace(manifest, changes=(InjectChange(
        target="arm9", symbol_file="analysis/symbols.json", hook="HookSite",
        expected=b"\x00\x00\x00\x00", script="asm/payload.asm", cave="auto", reserve=16, fill=0,
    ),), tools=ToolsConfig(armips=armips))
    write_manifest(project, manifest)

    with pytest.raises(PatchMismatchError, match="expected bytes"):
        build_project(project)
    assert not (project / "build/output/source-modded.nds").exists()
