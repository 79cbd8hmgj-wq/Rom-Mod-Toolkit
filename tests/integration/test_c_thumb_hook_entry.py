from __future__ import annotations

import json
import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from rommod.platforms.nds.binaries import get_main_binary, set_main_binary
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.build import build_project
from rommod.projects.manifest import CInjectChange, ToolsConfig, write_manifest
from rommod.projects.project import init_project


def _tool(name: str, env: str) -> str:
    value = os.environ.get(env) or shutil.which(name)
    if not value:
        pytest.skip(f"{name} executable not available")
    return str(Path(value).absolute())


def _tools() -> ToolsConfig:
    return ToolsConfig(
        armips=_tool("armips", "ROMMOD_ARMIPS"),
        clang=_tool("clang", "ROMMOD_CLANG"),
        ld_lld=_tool("ld.lld", "ROMMOD_LD_LLD"),
        llvm_objcopy=_tool("llvm-objcopy", "ROMMOD_LLVM_OBJCOPY"),
    )


def _write_thumb_hook_symbol(project: Path) -> None:
    (project / "analysis").mkdir()
    (project / "analysis/symbols.json").write_text(
        json.dumps({"symbols": [{
            "component": "arm9",
            "address": 0x02000004,
            "offset": 4,
            "name": "ThumbHook",
            "kind": "function",
            "instruction_set": "thumb",
            "confidence": "high",
            "evidence": ["test"],
        }]}),
        encoding="utf-8",
    )
    (project / "src").mkdir()
    (project / "src/payload.c").write_text(
        "int rommod_payload(int x) { return x + 7; }\n",
        encoding="utf-8",
    )


def test_c_inject_enters_arm_payload_from_short_thumb_hook(synthetic_rom_path: Path, tmp_path: Path):
    rom = NdsRom.load(synthetic_rom_path)
    set_main_binary(rom, "arm9", get_main_binary(rom, "arm9") + b"\x00" * 64)
    source = tmp_path / "source-thumb-c.nds"
    source.write_bytes(rom.serialize())

    project = tmp_path / "mod-thumb-c"
    manifest = init_project(source, project)
    _write_thumb_hook_symbol(project)
    manifest = replace(
        manifest,
        changes=(CInjectChange(
            target="arm9",
            symbol_file="analysis/symbols.json",
            hook="ThumbHook",
            expected=bytes.fromhex("05 06"),
            source="src/payload.c",
            cave="auto",
            reserve=32,
        ),),
        tools=_tools(),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")

    assert arm9[4:6] == bytes.fromhex("1C E0")
    assert arm9[64:68] == bytes.fromhex("78 47 C0 46")
    assert arm9[68:84] == bytes.fromhex(
        "02 00 00 EB 00 C0 9F E5 1C FF 2F E1 07 00 00 02"
    )
    assert arm9[84:92] == bytes.fromhex("07 00 80 E2 1E FF 2F E1")

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    c_run = report["c_injections"][0]
    assert c_run["hook_mode"] == "thumb-short"
    assert c_run["hook_size"] == 2
    assert c_run["scratch_register"] is None
    assert c_run["code_address"] == 0x02000054


def test_c_inject_enters_arm_payload_from_long_thumb_hook_with_scratch(synthetic_rom_path: Path, tmp_path: Path):
    rom = NdsRom.load(synthetic_rom_path)
    set_main_binary(
        rom,
        "arm9",
        get_main_binary(rom, "arm9") + b"\xAA" * 0x3000 + b"\x00" * 64,
    )
    source = tmp_path / "source-thumb-c-long.nds"
    source.write_bytes(rom.serialize())

    project = tmp_path / "mod-thumb-c-long"
    manifest = init_project(source, project)
    _write_thumb_hook_symbol(project)
    manifest = replace(
        manifest,
        changes=(CInjectChange(
            target="arm9",
            symbol_file="analysis/symbols.json",
            hook="ThumbHook",
            expected=bytes.fromhex("05 06 07 08 09 0A 0B 0C"),
            source="src/payload.c",
            cave="auto",
            reserve=32,
            scratch_register="r3",
        ),),
        tools=_tools(),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")

    assert arm9[4:8] == bytes.fromhex("00 4B 18 47")
    assert arm9[8:12] == (0x02003041).to_bytes(4, "little")
    assert arm9[0x3040:0x3044] == bytes.fromhex("78 47 C0 46")
    assert arm9[0x3044:0x3054] == bytes.fromhex(
        "02 00 00 EB 00 C0 9F E5 1C FF 2F E1 0D 00 00 02"
    )
    assert arm9[0x3054:0x305C] == bytes.fromhex("07 00 80 E2 1E FF 2F E1")

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    c_run = report["c_injections"][0]
    assert c_run["hook_mode"] == "thumb-long"
    assert c_run["hook_size"] == 8
    assert c_run["scratch_register"] == "r3"
    assert c_run["code_address"] == 0x02003054
