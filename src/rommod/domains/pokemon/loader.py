"""Load Pokémon decomp source data into normalized repository records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rommod.analysis.repository import load_json_document
from rommod.domains.pokemon.discovery import discover_move_files, discover_species_files
from rommod.domains.pokemon.models import (
    EvolutionRecord,
    LearnsetEntry,
    MoveRecord,
    RepositoryIndex,
    SpeciesRecord,
)
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


def _required_string(data: dict[str, Any], relative_path: Path, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        raise _fail(relative_path, field)
    return value


def _required_int(data: dict[str, Any], relative_path: Path, field: str) -> int:
    value = data.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise _fail(relative_path, field)
    return value


def _base_stats(data: dict[str, Any], relative_path: Path) -> tuple[int, int, int, int, int, int]:
    raw = data.get("base_stats")
    if not isinstance(raw, dict):
        raise _fail(relative_path, "base_stats")
    values: list[int] = []
    for field in _STAT_FIELDS:
        value = raw.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise _fail(relative_path, f"base_stats.{field}")
        values.append(value)
    return tuple(values)  # type: ignore[return-value]


def _display_name(data: dict[str, Any], relative_path: Path) -> str:
    pokedex_data = data.get("pokedex_data")
    if not isinstance(pokedex_data, dict):
        raise _fail(relative_path, "pokedex_data")
    english = pokedex_data.get("en")
    if not isinstance(english, dict):
        raise _fail(relative_path, "pokedex_data.en")
    name = english.get("name")
    if not isinstance(name, str) or not name:
        raise _fail(relative_path, "pokedex_data.en.name")
    return name


def _learnset(data: dict[str, Any], relative_path: Path) -> tuple[LearnsetEntry, ...]:
    learnset = data.get("learnset")
    if not isinstance(learnset, dict):
        raise _fail(relative_path, "learnset")
    raw = learnset.get("by_level")
    if not isinstance(raw, list):
        raise _fail(relative_path, "learnset.by_level")

    entries: list[LearnsetEntry] = []
    for index, item in enumerate(raw):
        field = f"learnset.by_level[{index}]"
        if not isinstance(item, list) or len(item) != 2:
            raise _fail(relative_path, field)
        level, move = item
        if not isinstance(level, int) or isinstance(level, bool) or level < 0:
            raise _fail(relative_path, field, "has an invalid level")
        if not isinstance(move, str) or not move:
            raise _fail(relative_path, field, "has an invalid move")
        entries.append(LearnsetEntry(level=level, move=move))
    return tuple(entries)


def _target_identifier(value: str) -> str:
    if value.startswith("SPECIES_"):
        value = value.removeprefix("SPECIES_")
    return value.casefold()


def _evolutions(data: dict[str, Any], relative_path: Path, source: str) -> tuple[EvolutionRecord, ...]:
    raw = data.get("evolutions", [])
    if not isinstance(raw, list):
        raise _fail(relative_path, "evolutions")

    records: list[EvolutionRecord] = []
    for index, item in enumerate(raw):
        field = f"evolutions[{index}]"
        if not isinstance(item, list) or len(item) not in (2, 3):
            raise _fail(relative_path, field)
        method = item[0]
        target = item[-1]
        if not isinstance(method, str) or not method:
            raise _fail(relative_path, field, "has an invalid method")
        if not isinstance(target, str) or not target:
            raise _fail(relative_path, field, "has an invalid target")

        parameter = item[1] if len(item) == 3 else None
        level = parameter if isinstance(parameter, int) and not isinstance(parameter, bool) and parameter >= 0 else None
        records.append(
            EvolutionRecord(
                source=source,
                target=_target_identifier(target),
                method=method,
                level=level,
            )
        )
    return tuple(records)


def _species_from_file(root: Path, path: Path) -> tuple[SpeciesRecord, tuple[EvolutionRecord, ...]]:
    document = load_json_document(root, path)
    relative = document.relative_path
    data = document.data

    identifier = path.parent.name.casefold()
    record = SpeciesRecord(
        identifier=identifier,
        display_name=_display_name(data, relative),
        source_path=relative,
        types=_string_list(data, relative, "types"),
        base_stats=_base_stats(data, relative),
        abilities=_string_list(data, relative, "abilities"),
        level_up_moves=_learnset(data, relative),
    )
    return record, _evolutions(data, relative, identifier)


def _move_from_file(root: Path, path: Path) -> MoveRecord:
    document = load_json_document(root, path)
    relative = document.relative_path
    data = document.data
    return MoveRecord(
        identifier=path.parent.name.casefold(),
        display_name=_required_string(data, relative, "name"),
        move_type=_required_string(data, relative, "type"),
        category=_required_string(data, relative, "class"),
        power=_required_int(data, relative, "power"),
        accuracy=_required_int(data, relative, "accuracy"),
        pp=_required_int(data, relative, "pp"),
        source_path=relative,
    )


def load_repository_index(root: Path) -> RepositoryIndex:
    """Build the normalized, read-only Pokémon source index for *root*."""

    resolved_root = root.resolve()
    species: dict[str, SpeciesRecord] = {}
    evolutions: list[EvolutionRecord] = []
    for path in discover_species_files(resolved_root):
        record, record_evolutions = _species_from_file(resolved_root, path)
        if record.identifier in species:
            raise RomModError(f"duplicate species identifier: {record.identifier}")
        species[record.identifier] = record
        evolutions.extend(record_evolutions)

    moves: dict[str, MoveRecord] = {}
    for path in discover_move_files(resolved_root):
        record = _move_from_file(resolved_root, path)
        if record.identifier in moves:
            raise RomModError(f"duplicate move identifier: {record.identifier}")
        moves[record.identifier] = record

    warnings: tuple[str, ...] = ()
    if not moves:
        warnings = ("Move metadata was not discovered; move-aware analysis will be limited.",)

    return RepositoryIndex(
        root=resolved_root,
        species=species,
        moves=moves,
        evolutions=tuple(evolutions),
        warnings=warnings,
    )
