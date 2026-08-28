from pathlib import Path

import pytest

from rommod.core.hashes import sha256_file
from rommod.errors import SourceMismatchError
from rommod.projects.project import init_project, verify_source


def test_init_locks_source_hash_and_creates_layout(tmp_path: Path):
    source = tmp_path / "game.nds"
    source.write_bytes(b"synthetic-source")
    project = tmp_path / "mod"

    manifest = init_project(source, project)

    assert manifest.platform == "nds"
    assert manifest.source.sha256 == sha256_file(source)
    assert (project / "rommod.yaml").is_file()
    for relative in (
        "patches", "asm", "files", "build/extracted", "build/work", "build/output", "reports"
    ):
        assert (project / relative).is_dir()
    assert source.read_bytes() == b"synthetic-source"


def test_verify_source_rejects_hash_change(tmp_path: Path):
    source = tmp_path / "game.nds"
    source.write_bytes(b"one")
    project = tmp_path / "mod"
    manifest = init_project(source, project)
    source.write_bytes(b"two")

    with pytest.raises(SourceMismatchError):
        verify_source(project, manifest)
