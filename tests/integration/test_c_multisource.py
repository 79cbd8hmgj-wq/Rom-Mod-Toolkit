from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

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


def test_compile_links_multiple_c_translation_units(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.c").write_text(
        "extern int helper(int);\n"
        "int rommod_payload(int x) { return helper(x) + 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "src/helper.c").write_text(
        "int helper(int x) { return x * 3; }\n",
        encoding="utf-8",
    )

    result = compile_arm_c_payload(
        tmp_path,
        None,
        sources=("src/payload.c", "src/helper.c"),
        load_address=0x02000048,
        capacity=64,
        tools=_tools(),
        job_index=0,
    )

    assert 0 < len(result.binary) <= 64
    assert result.load_address == 0x02000048
