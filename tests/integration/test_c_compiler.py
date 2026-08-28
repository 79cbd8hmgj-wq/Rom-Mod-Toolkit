from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from rommod.errors import ExternalToolError
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


def test_compile_freestanding_arm_c_payload(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.c").write_text(
        "int rommod_payload(int x) { return x + 7; }\n",
        encoding="utf-8",
    )
    result = compile_arm_c_payload(
        tmp_path,
        "src/payload.c",
        load_address=0x02000048,
        capacity=24,
        tools=_tools(),
        job_index=0,
    )
    assert 0 < len(result.binary) <= 24
    assert result.load_address == 0x02000048
    assert result.binary.endswith(bytes.fromhex("1E FF 2F E1"))
    assert "clang version" in result.clang_version.lower()
    assert "lld" in result.lld_version.lower()


def test_compile_rejects_writable_globals(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.c").write_text(
        "int state; int rommod_payload(int x) { state += x; return state; }\n",
        encoding="utf-8",
    )
    with pytest.raises(ExternalToolError, match="bss|writable data"):
        compile_arm_c_payload(
            tmp_path,
            "src/payload.c",
            load_address=0x02000048,
            capacity=64,
            tools=_tools(),
            job_index=0,
        )


def test_compile_links_imported_arm_game_symbol(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.c").write_text(
        "extern int GameHelper(int); int rommod_payload(int x) { return GameHelper(x); }\n",
        encoding="utf-8",
    )
    result = compile_arm_c_payload(
        tmp_path,
        "src/payload.c",
        load_address=0x02000048,
        capacity=24,
        tools=_tools(),
        job_index=0,
        link_symbols={"GameHelper": 0x02000020},
    )
    assert 0 < len(result.binary) <= 24
