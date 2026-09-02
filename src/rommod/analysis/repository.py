"""Guarded access to structured source files inside a repository."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rommod.errors import SourceMismatchError


_INDENT_RE = re.compile(r"^(?P<indent>[ \t]+)\S", re.MULTILINE)


@dataclass(frozen=True)
class RepositorySnapshot:
    """A resolved repository root used as the boundary for source operations."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())


@dataclass(frozen=True)
class SourceDocument:
    """Parsed JSON together with the source metadata needed for a guarded write."""

    relative_path: Path
    data: dict[str, Any]
    sha256: str
    indent: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_path(root: Path, path: Path) -> tuple[Path, Path]:
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        relative = resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"{path} is outside repository {resolved_root}") from exc
    return resolved_path, relative


def _detect_indent(text: str) -> int:
    match = _INDENT_RE.search(text)
    if match is None:
        return 2
    whitespace = match.group("indent")
    if "\t" in whitespace:
        return 4
    return max(1, len(whitespace))


def load_json_document(root: Path, path: Path) -> SourceDocument:
    """Load a JSON object from inside *root* and capture its guarded-write metadata."""

    resolved_path, relative = _relative_path(root, path)
    raw = resolved_path.read_bytes()
    text = raw.decode("utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{relative.as_posix()} must contain a JSON object")
    return SourceDocument(
        relative_path=relative,
        data=data,
        sha256=_sha256(raw),
        indent=_detect_indent(text),
    )


def write_json_document(
    snapshot: RepositorySnapshot,
    document: SourceDocument,
    new_data: dict[str, Any],
) -> str:
    """Atomically replace a loaded JSON document if its source hash is unchanged."""

    target, relative = _relative_path(snapshot.root, snapshot.root / document.relative_path)
    current = target.read_bytes()
    if _sha256(current) != document.sha256:
        raise SourceMismatchError(f"{relative.as_posix()} changed since it was loaded")

    serialized = (json.dumps(new_data, indent=document.indent, ensure_ascii=False) + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise

    return _sha256(serialized)
