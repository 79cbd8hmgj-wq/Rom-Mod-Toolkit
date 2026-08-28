from __future__ import annotations

from pathlib import Path

import pytest

from rommod.errors import ExternalToolError
from rommod.platforms.nds.c_compiler import compile_arm_c_payload
from rommod.projects.manifest import ToolsConfig


def _tools() -> ToolsConfig:
    return ToolsConfig(
        clang="/usr/local/swift/usr/bin/clang",
        ld_lld="/usr/local/swift/usr/bin/ld.lld",
        llvm_objcopy="/usr/local/swift/usr/bin/llvm-objcopy",
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
