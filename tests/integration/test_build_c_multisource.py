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


def test_build_injects_multiple_c_translation_units(synthetic_rom_path: Path, tmp_path: Path):
    rom = NdsRom.load(synthetic_rom_path)
    set_main_binary(rom, "arm9", get_main_binary(rom, "arm9") + b"\x00" * 96)
    source_rom = tmp_path / "source-multi.nds"
    source_rom.write_bytes(rom.serialize())

    project = tmp_path / "mod"
    manifest = init_project(source_rom, project)
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
        }]}),
        encoding="utf-8",
    )
    (project / "src").mkdir()
    (project / "src/payload.c").write_text(
        "extern int helper(int);\n"
        "int rommod_payload(int x) { return helper(x) + 1; }\n",
        encoding="utf-8",
    )
    (project / "src/helper.c").write_text(
        "int helper(int x) { return x * 3; }\n",
        encoding="utf-8",
    )
    manifest = replace(
        manifest,
        changes=(CInjectChange(
            target="arm9",
            symbol_file="analysis/symbols.json",
            hook="HookSite",
            expected=bytes.fromhex("05 06 07 08"),
            source=None,
            sources=("src/payload.c", "src/helper.c"),
            cave="auto",
            reserve=64,
        ),),
        tools=_tools(),
    )
    write_manifest(project, manifest)

    result = build_project(project)
    rebuilt = NdsRom.load(result.output_path)
    arm9 = get_main_binary(rebuilt, "arm9")
    assert arm9[4:8] == bytes.fromhex("15 00 00 EA")

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    change_report = report["changes"][0]
    assert change_report["sources"] == ["src/payload.c", "src/helper.c"]
    assert report["c_injections"][0]["payload_size"] > 8
