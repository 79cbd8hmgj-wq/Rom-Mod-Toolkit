"""Project-path safety helpers."""

from __future__ import annotations

from pathlib import Path

from rommod.errors import ManifestError


def resolve_inside(root: Path, relative: str | Path) -> Path:
    root = Path(root).resolve()
    candidate = (root / Path(relative)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ManifestError(f"Path escapes project root: {relative}")
    return candidate
