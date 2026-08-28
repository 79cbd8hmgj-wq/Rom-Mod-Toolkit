from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from rommod.platforms.nds.binaries import get_main_binary, set_main_binary
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.build import build_project
from rommod.projects.manifest import CInjectChange, ToolsConfig, write_manifest
from rommod.projects.project import init_project


TOOLS = ToolsConfig(
    armips="/mnt/data/armips-build/armips",
    clang="/usr/local/swift/usr/bin/clang",
    ld_lld="/usr/local/swift/usr/bin/ld.lld",
    llvm_objcopy="/usr/local/swift/usr/bin/llvm-objcopy",
)


def test_build_injects_freestanding_arm_c_payload(synthetic_rom_path: Path, tmp_path: Path):
    rom = NdsRom.load(synthetic_rom_path)
    set_main_binary(rom, "arm9", get_main_binary(rom, "arm9") + b"\x00" * 64)
    source = tmp_path / "source.nds"
    source.write_bytes(rom.serialize())

    project = tmp_path / "mod"
    manifest = init_project(source, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(
        json.dumps([{
            "component": "arm9",
            "address": 0x02000004,
            "offset": 4,
            "name": "HookSite",
            "kind": "function",
            "instruction_set": "arm",
            "confidence": "high",
            "evidence": ["test"],
        }]),
        encoding="utf-8",
    )
    (project / "src").mkdir()
    (project / "src/payload.c").write_text(
        "int rommod_payload(int x) { return x + 7; }\n",
        encoding="utf-8",
    )
    manifest = replace(
        manifest,
        changes=(CInjectChange(
            target="arm9",
            symbol_file="analysis/symbols.json",
            hook="HookSite",
            expected=bytes.fromhex("05 06 07 08"),
            source="src/payload.c",
            cave="auto",
            reserve=32,
        ),),
        tools=TOOLS,
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")
    assert arm9[4:8] == bytes.fromhex("0D 00 00 EA")
    assert arm9[64:72] == bytes.fromhex("00 00 00 EB EF FF FF EA")
    assert arm9[72:80] == bytes.fromhex("07 00 80 E2 1E FF 2F E1")

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    c_run = report["c_injections"][0]
    assert c_run["hook_address"] == 0x02000004
    assert c_run["cave_address"] == 0x02000040
    assert c_run["code_address"] == 0x02000048
    assert c_run["payload_size"] == 8
    assert "clang" in report["tools"]
    assert "ld_lld" in report["tools"]
    assert "llvm_objcopy" in report["tools"]


def test_build_c_payload_links_validated_arm_game_symbol(synthetic_rom_path: Path, tmp_path: Path):
    rom = NdsRom.load(synthetic_rom_path)
    set_main_binary(rom, "arm9", get_main_binary(rom, "arm9") + b"\x00" * 64)
    source = tmp_path / "source-symbol.nds"
    source.write_bytes(rom.serialize())

    project = tmp_path / "mod-symbol"
    manifest = init_project(source, project)
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(
        json.dumps({"symbols": [
            {
                "component": "arm9",
                "address": 0x02000004,
                "offset": 4,
                "name": "HookSite",
                "kind": "function",
                "instruction_set": "arm",
                "confidence": "high",
                "evidence": ["test"],
            },
            {
                "component": "arm9",
                "address": 0x02000020,
                "offset": 0x20,
                "name": "GameHelper",
                "kind": "function",
                "instruction_set": "arm",
                "confidence": "high",
                "evidence": ["test"],
            },
        ]}),
        encoding="utf-8",
    )
    (project / "src").mkdir()
    (project / "src/payload.c").write_text(
        "extern int GameHelper(int);\n"
        "int rommod_payload(int x) { return GameHelper(x); }\n",
        encoding="utf-8",
    )
    manifest = replace(
        manifest,
        changes=(CInjectChange(
            target="arm9",
            symbol_file="analysis/symbols.json",
            hook="HookSite",
            expected=bytes.fromhex("05 06 07 08"),
            source="src/payload.c",
            cave="auto",
            reserve=32,
        ),),
        tools=TOOLS,
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")
    assert arm9[72:76] == bytes.fromhex("F4 FF FF EA")
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["c_injections"][0]["payload_size"] == 4
