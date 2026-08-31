from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from rommod.errors import BuildError
from rommod.platforms.nds.c_compiler import compile_arm_c_payload
from rommod.projects.manifest import ToolsConfig


def _tool(name: str, env: str) -> str:
    value = os.environ.get(env) or shutil.which(name)
    if not value:
        pytest.skip(f"{name} executable not available")
    return str(Path(value).absolute())


def _tools() -> ToolsConfig:
    return ToolsConfig(
        clang=_tool("clang", "ROMMOD_CLANG"),
        ld_lld=_tool("ld.lld", "ROMMOD_LD_LLD"),
        llvm_objcopy=_tool("llvm-objcopy", "ROMMOD_LLVM_OBJCOPY"),
    )


def _write_source(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.c").write_text(
        "#ifndef ROMMOD_MULTIPLIER\n"
        "#error ROMMOD_MULTIPLIER must be defined\n"
        "#endif\n"
        "#ifndef GAME_REGION_US\n"
        "#error GAME_REGION_US must be defined\n"
        "#endif\n"
        "int rommod_payload(int x) { return x * ROMMOD_MULTIPLIER + GAME_REGION_US; }\n",
        encoding="utf-8",
    )


def test_compile_passes_defines_to_every_translation_unit(tmp_path: Path):
    _write_source(tmp_path)
    result = compile_arm_c_payload(
        tmp_path,
        "src/payload.c",
        defines=("ROMMOD_MULTIPLIER=3", "GAME_REGION_US=1"),
        load_address=0x02000048,
        capacity=64,
        tools=_tools(),
        job_index=0,
    )
    assert 0 < len(result.binary) <= 64


def test_compile_rejects_invalid_define_name(tmp_path: Path):
    _write_source(tmp_path)
    with pytest.raises(BuildError, match="define"):
        compile_arm_c_payload(
            tmp_path,
            "src/payload.c",
            defines=("BAD-NAME=1",),
            load_address=0x02000048,
            capacity=64,
            tools=_tools(),
            job_index=0,
        )
