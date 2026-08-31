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


def test_compile_explicit_cpp_language_for_extensionless_source(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.inc").write_text(
        "template<int N> struct Add {\n"
        "  static constexpr int apply(int x) { return x + N; }\n"
        "};\n"
        'extern "C" int rommod_payload(int x) { return Add<7>::apply(x); }\n',
        encoding="utf-8",
    )

    result = compile_arm_c_payload(
        tmp_path,
        "src/payload.inc",
        language="cpp",
        load_address=0x02000040,
        capacity=64,
        tools=_tools(),
        job_index=0,
    )
    assert 0 < len(result.binary) <= 64


def test_cpp_mode_disables_exception_runtime(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/payload.inc").write_text(
        'extern "C" int rommod_payload(int x) { if (x) throw x; return 0; }\n',
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="exception|exceptions"):
        compile_arm_c_payload(
            tmp_path,
            "src/payload.inc",
            language="cpp",
            load_address=0x02000040,
            capacity=64,
            tools=_tools(),
            job_index=0,
        )
