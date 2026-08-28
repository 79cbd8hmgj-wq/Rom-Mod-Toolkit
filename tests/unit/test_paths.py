from pathlib import Path

import pytest

from rommod.core.paths import resolve_inside
from rommod.errors import ManifestError


def test_resolve_inside_rejects_escape(tmp_path: Path):
    with pytest.raises(ManifestError):
        resolve_inside(tmp_path, "../escape.bin")


def test_resolve_inside_accepts_child(tmp_path: Path):
    assert resolve_inside(tmp_path, "build/out.nds") == (tmp_path / "build/out.nds").resolve()
