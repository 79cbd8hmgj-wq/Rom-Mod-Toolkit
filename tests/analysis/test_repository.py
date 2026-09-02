from __future__ import annotations

import json
from pathlib import Path

import pytest

from rommod.analysis.repository import RepositorySnapshot, load_json_document, write_json_document
from rommod.errors import SourceMismatchError


def test_load_json_document_captures_relative_path_hash_and_indent(tmp_path: Path) -> None:
    path = tmp_path / "res" / "pokemon" / "persian" / "data.json"
    path.parent.mkdir(parents=True)
    path.write_text('{\n  "name": "Persian"\n}\n', encoding="utf-8")

    snapshot = RepositorySnapshot(tmp_path)
    document = load_json_document(snapshot.root, path)

    assert document.relative_path.as_posix() == "res/pokemon/persian/data.json"
    assert document.data["name"] == "Persian"
    assert len(document.sha256) == 64
    assert document.indent == 2


def test_load_json_document_rejects_path_outside_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="outside repository"):
        load_json_document(root, outside)


def test_write_json_document_aborts_when_source_changed_after_load(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{\n  "value": 1\n}\n', encoding="utf-8")
    snapshot = RepositorySnapshot(tmp_path)
    document = load_json_document(snapshot.root, path)

    path.write_text('{\n  "value": 999\n}\n', encoding="utf-8")

    with pytest.raises(SourceMismatchError, match="changed since it was loaded"):
        write_json_document(snapshot, document, {"value": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"value": 999}


def test_write_json_document_preserves_indent_and_returns_new_hash(tmp_path: Path) -> None:
    path = tmp_path / "data.json"
    path.write_text('{\n    "value": 1\n}\n', encoding="utf-8")
    snapshot = RepositorySnapshot(tmp_path)
    document = load_json_document(snapshot.root, path)

    new_hash = write_json_document(snapshot, document, {"value": 2, "extra": True})

    assert len(new_hash) == 64
    assert path.read_text(encoding="utf-8") == '{\n    "value": 2,\n    "extra": true\n}\n'
