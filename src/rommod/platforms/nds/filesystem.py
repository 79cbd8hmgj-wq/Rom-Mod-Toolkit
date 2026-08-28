"""NitroFS enumeration, extraction, and replacement."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rommod.core.paths import resolve_inside
from rommod.errors import TargetNotFoundError
from rommod.platforms.nds.rom import NdsRom


@dataclass(frozen=True)
class NdsFileEntry:
    path: str
    file_id: int
    size: int


def _normalize(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        raise TargetNotFoundError("NitroFS path is empty")
    return normalized


def list_files(rom: NdsRom) -> tuple[NdsFileEntry, ...]:
    entries: list[NdsFileEntry] = []
    backend = rom._nds
    for file_id, data in enumerate(backend.files):
        path = backend.filenames.filenameOf(file_id)
        if path is not None:
            entries.append(NdsFileEntry(path=path, file_id=file_id, size=len(data)))
    return tuple(entries)


def extract_files(rom: NdsRom, destination: Path) -> list[Path]:
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    backend = rom._nds
    for entry in list_files(rom):
        output = resolve_inside(destination, entry.path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(backend.files[entry.file_id])
        written.append(output)
    return written


def replace_file(rom: NdsRom, target: str, data: bytes) -> None:
    normalized = _normalize(target)
    try:
        rom._nds.setFileByName(normalized, bytes(data))
    except ValueError as exc:
        raise TargetNotFoundError(f"NitroFS file not found: {normalized}") from exc
