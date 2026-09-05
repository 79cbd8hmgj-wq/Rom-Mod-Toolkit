"""Checkpoint, compare, and guarded restore workflows for source projects."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from rommod.core.hashes import sha256_file
from rommod.domains.pokemon.diff import RepositoryDiff, diff_repositories
from rommod.errors import RomModError


_CHECKPOINT_COMPONENTS = (
    Path("res/pokemon"),
    Path("res/moves"),
)


@dataclass(frozen=True)
class CheckpointResult:
    directory: Path
    file_count: int


@dataclass(frozen=True)
class RestoreResult:
    checkpoint: Path
    restored_files: int


def _slug(label: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9._-]+", "_", label.strip()).strip("._-")
    if not compact:
        raise RomModError("checkpoint name must contain at least one letter or number")
    return compact


def _json_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for component in _CHECKPOINT_COMPONENTS:
        base = root / component
        if not base.is_dir():
            continue
        files.extend(path for path in base.rglob("*") if path.is_file())
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def _snapshot_hashes(root: Path, files: tuple[Path, ...]) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in files
    }


def _copy_source_snapshot(root: Path, checkpoint: Path, files: tuple[Path, ...]) -> None:
    source_root = checkpoint / "source"
    for path in files:
        relative = path.relative_to(root)
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _previous_checkpoint(root: Path, current: Path) -> Path | None:
    checkpoint_root = root / "checkpoints"
    if not checkpoint_root.is_dir():
        return None
    candidates = [
        path
        for path in checkpoint_root.iterdir()
        if path.is_dir()
        and path != current
        and (path / "metadata.json").is_file()
        and (path / "source").is_dir()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def _diff_payload(previous: Path | None, current: Path) -> dict[str, object]:
    if previous is None:
        return {
            "domain": "pokemon",
            "before_checkpoint": None,
            "after_checkpoint": str(current),
            "changed_species": 0,
            "species": [],
        }
    payload = diff_repositories(previous / "source", current / "source").to_dict()
    payload["before_checkpoint"] = str(previous)
    payload["after_checkpoint"] = str(current)
    return payload


def _render_diff_html(name: str, changes: dict[str, object]) -> str:
    body = escape(json.dumps(changes, indent=2, sort_keys=True))
    return (
        "<!doctype html>\n"
        "<html><head><meta charset=\"utf-8\"><title>"
        + escape(name)
        + "</title></head><body><h1>"
        + escape(name)
        + "</h1><pre>"
        + body
        + "</pre></body></html>\n"
    )


def create_checkpoint(root: Path, name: str) -> CheckpointResult:
    """Snapshot source data and current build metadata under checkpoints/<name>."""

    root = Path(root).resolve()
    if not root.is_dir():
        raise RomModError(f"project root does not exist: {root}")

    files = _source_files(root)
    if not files:
        raise RomModError("no checkpointable source data found under res/pokemon or res/moves")

    checkpoint = root / "checkpoints" / _slug(name)
    if checkpoint.exists():
        raise RomModError(f"checkpoint already exists: {checkpoint.name}")
    checkpoint.mkdir(parents=True)

    hashes = _snapshot_hashes(root, files)
    _copy_source_snapshot(root, checkpoint, files)

    metadata = {
        "name": name,
        "directory": str(checkpoint),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(files),
    }
    _json_write(checkpoint / "metadata.json", metadata)
    _json_write(checkpoint / "hashes.json", hashes)

    build_report = root / "rommod" / "reports" / "build.json"
    if build_report.is_file():
        shutil.copy2(build_report, checkpoint / "build.json")

    previous = _previous_checkpoint(root, checkpoint)
    changes = _diff_payload(previous, checkpoint)
    _json_write(checkpoint / "changes.json", changes)
    (checkpoint / "diff.html").write_text(
        _render_diff_html(name, changes),
        encoding="utf-8",
    )
    return CheckpointResult(directory=checkpoint, file_count=len(files))


def compare_checkpoints(before: Path, after: Path) -> RepositoryDiff:
    """Compare two checkpoint source snapshots using the semantic Pokémon diff."""

    before = Path(before).resolve()
    after = Path(after).resolve()
    for checkpoint in (before, after):
        if not (checkpoint / "source").is_dir():
            raise RomModError(f"invalid checkpoint (missing source snapshot): {checkpoint}")
    return diff_repositories(before / "source", after / "source")


def restore_checkpoint(root: Path, checkpoint: Path) -> RestoreResult:
    """Restore a checkpoint after verifying every snapshot file against its pinned hash."""

    root = Path(root).resolve()
    checkpoint = Path(checkpoint).resolve()
    source = checkpoint / "source"
    hashes_path = checkpoint / "hashes.json"
    if not source.is_dir() or not hashes_path.is_file():
        raise RomModError(f"invalid checkpoint: {checkpoint}")

    raw_hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    if not isinstance(raw_hashes, dict):
        raise RomModError("checkpoint hashes.json must contain an object")

    verified: list[tuple[Path, Path]] = []
    for raw_relative, expected in sorted(raw_hashes.items()):
        if not isinstance(raw_relative, str) or not isinstance(expected, str):
            raise RomModError("checkpoint hashes.json contains invalid entries")
        relative = Path(raw_relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise RomModError(f"unsafe checkpoint path: {raw_relative}")
        snapshot_file = (source / relative).resolve()
        try:
            snapshot_file.relative_to(source.resolve())
        except ValueError as exc:
            raise RomModError(f"unsafe checkpoint path: {raw_relative}") from exc
        if not snapshot_file.is_file():
            raise RomModError(f"checkpoint snapshot file is missing: {raw_relative}")
        actual = sha256_file(snapshot_file)
        if actual != expected:
            raise RomModError(f"checkpoint snapshot hash mismatch: {raw_relative}")
        destination = (root / relative).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise RomModError(f"unsafe restore path: {raw_relative}") from exc
        verified.append((snapshot_file, destination))

    for snapshot_file, destination in verified:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot_file, destination)

    return RestoreResult(checkpoint=checkpoint, restored_files=len(verified))
