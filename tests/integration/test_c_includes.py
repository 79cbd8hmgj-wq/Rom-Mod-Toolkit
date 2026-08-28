from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from rommod.errors import BuildError, ManifestError
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


def _write_project(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "include").mkdir()
    (tmp_path / "include/mod_api.h").write_text(
        "int helper(int x);\n",
        encoding="utf-8",
    )
    (tmp_path / "src/payload.c").write_text(
        '#include "mod_api.h"\n'
        "int rommod_payload(int x) { return helper(x) + 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "src/helper.c").write_text(
        '#include "mod_api.h"\n'
        "int helper(int x) { return x * 3; }\n",
        encoding="utf-8",
    )


def test_compile_uses_shared_include_dirs_for_all_translation_units(tmp_path: Path):
    _write_project(tmp_path)
    result = compile_arm_c_payload(
        tmp_path,
        None,
        sources=("src/payload.c", "src/helper.c"),
        include_dirs=("include",),
        load_address=0x02000048,
        capacity=64,
        tools=_tools(),
        job_index=0,
    )
    assert 0 < len(result.binary) <= 64


def test_compile_rejects_missing_include_directory(tmp_path: Path):
    _write_project(tmp_path)
    with pytest.raises(BuildError, match="include directory"):
        compile_arm_c_payload(
            tmp_path,
            None,
            sources=("src/payload.c", "src/helper.c"),
            include_dirs=("missing",),
            load_address=0x02000048,
            capacity=64,
            tools=_tools(),
            job_index=0,
        )


def test_compile_rejects_include_directory_outside_project(tmp_path: Path):
    _write_project(tmp_path)
    with pytest.raises(ManifestError, match="escapes project root"):
        compile_arm_c_payload(
            tmp_path,
            None,
            sources=("src/payload.c", "src/helper.c"),
            include_dirs=("../outside",),
            load_address=0x02000048,
            capacity=64,
            tools=_tools(),
            job_index=0,
        )
