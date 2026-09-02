"""Load Pokémon decomp source data into normalized repository records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rommod.analysis.repository import load_json_document
from rommod.domains.pokemon.discovery import discover_species_files
from rommod.domains.pokemon.models import LearnsetEntry, RepositoryIndex, SpeciesRecord
from rommod.errors import RomModError


_STAT_FIELDS = (
    "hp",
    "attack",
    "defense",
    "special_attack",
    "special_defense",
    "speed",
)


def _fail(relative_path: Path, field: str, detail: str = "is missing or malformed") -> RomModError:
    return RomModError(f"{relative_path.as_posix()}: {field} {detail}")


def _string_list(data: dict[str, Any], relative_path: Path, field: str) -> tuple[str, ...]:
    value = data.get(field)
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item for item in value):
        raise _fail(relative_path, field)
    return tuple(value)


def _base_stats(data: dict[str, Any], relative_path: Path) -> tuple[int, int, int, int, int, int]:
    raw = data.get("base_stats")
    if not isinstance(raw, dict):
        raise _fail(relative_path, "base_stats")
    values: list[int] = []
    for field in _STAT_FIELDS:
        value = raw.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise _fail(relative_path, field)
        values.append(value)
    return tuple(values)  # type: ignore[return-value]


def _learnset(data: dict[str, Any], relative_path: Path) -> tuple[LearnsetEntry, ...]:
    raw = data.get("level_up_moves")
    if not isinstance(raw, list):
        raise _fail(relative_path, "level_up_moves")

    entries: list[LearnsetEntry] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise _fail(relative_path, f"level_up_moves[{index}]")
        level = item.get("level")
        move = item.get("move")
        if not isinstance(level, int) or isinstance(level, bool) or level < 0:
            raise _fail(relative_path, f"level_up_moves[{index}].level")
        if not isinstance(move, str) or not move:
            raise _fail(relative_path, f"level_up_moves[{index}].move")
        entries.append(LearnsetEntry(level=level, move=move))
    return tuple(entries)


def _species_from_file(root: Path, path: Path) -> SpeciesRecord:
    document = load_json_document(root, path)
    relative = document.relative_path
    data = document.data

    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise _fail(relative, "name")

    identifier = path.parent.name.casefold()
    return SpeciesRecord(
        identifier=identifier,
        display_name=name,
        source_path=relative,
        types=_string_list(data, relative, "types"),
        base_stats=_base_stats(data, relative),
        abilities=_string_list(data, relative, "abilities"),
        level_up_moves=_learnset(data, relative),
    )


def load_repository_index(root: Path) -> RepositoryIndex:
    """Build the first normalized, read-only Pokémon index for *root*."""

    resolved_root = root.resolve()
    species: dict[str, SpeciesRecord] = {}
    for path in discover_species_files(resolved_root):
        record = _species_from_file(resolved_root, path)
        if record.identifier in species:
            raise RomModError(f"duplicate species identifier: {record.identifier}")
        species[record.identifier] = record

    warnings = (
        "Move metadata was not discovered; move-aware analysis will be limited.",
    )
    return RepositoryIndex(
        root=resolved_root,
        species=species,
        moves={},
        evolutions=(),
        warnings=warnings,
    )
