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


def test_c_injection_builds_arm_to_thumb_call_veneer(synthetic_rom_path: Path, tmp_path: Path):
    rom = NdsRom.load(synthetic_rom_path)
    set_main_binary(rom, "arm9", get_main_binary(rom, "arm9") + b"\x00" * 96)
    source = tmp_path / "source.nds"
    source.write_bytes(rom.serialize())

    project = tmp_path / "mod"
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
                "name": "ThumbHelper",
                "kind": "function",
                "instruction_set": "thumb",
                "confidence": "high",
                "evidence": ["test"],
            },
        ]}),
        encoding="utf-8",
    )
    (project / "src").mkdir()
    (project / "src/payload.c").write_text(
        "extern int ThumbHelper(int);\n"
        "int rommod_payload(int x) { return ThumbHelper(x); }\n",
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
            reserve=48,
        ),),
        tools=_tools(),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")

    assert arm9[4:8] == bytes.fromhex("0D 00 00 EA")
    assert arm9[64:72] == bytes.fromhex("03 00 00 EB EF FF FF EA")
    assert arm9[72:84] == bytes.fromhex("00 C0 9F E5 1C FF 2F E1 21 00 00 02")
    assert arm9[84:88] == bytes.fromhex("FB FF FF EA")

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    c_run = report["c_injections"][0]
    assert c_run["code_address"] == 0x02000054
    assert c_run["thumb_veneers"] == 1
    assert c_run["veneer_bytes"] == 12
