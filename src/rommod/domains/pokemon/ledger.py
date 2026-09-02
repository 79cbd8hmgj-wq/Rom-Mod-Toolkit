"""Guarded execution of approved Pokémon source-edit ledgers."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rommod.analysis.repository import (
    RepositorySnapshot,
    SourceDocument,
    load_json_document,
    write_json_document,
)
from rommod.errors import RomModError, SourceMismatchError


_IDENTIFIER_RE = re.compile(r"^[a-z0-9_]+$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SUPPORTED_OPERATIONS = {
    "insert_level_move",
    "replace_level_move",
    "remove_level_move",
}


@dataclass(frozen=True)
class LedgerChange:
    species: str
    operation: str
    before: tuple[int, str] | None = None
    after: tuple[int, str] | None = None
    source_sha256: str | None = None


@dataclass(frozen=True)
class PokemonLedger:
    version: int
    domain: str
    changes: tuple[LedgerChange, ...]


@dataclass(frozen=True)
class PlannedChange:
    species: str
    operation: str
    before: tuple[int, str] | None
    after: tuple[int, str] | None


@dataclass(frozen=True)
class PlannedFile:
    source_path: Path
    source_sha256: str
    result_sha256: str
    changes: tuple[PlannedChange, ...]


@dataclass(frozen=True)
class LedgerPlan:
    files: tuple[PlannedFile, ...]
    applied: bool = False


@dataclass(frozen=True)
class _PreparedFile:
    document: SourceDocument
    new_data: dict[str, Any]
    planned: PlannedFile


def _error(detail: str) -> RomModError:
    return RomModError(f"invalid pokemon ledger: {detail}")


def _parse_entry(value: Any, field: str) -> tuple[int, str]:
    if not isinstance(value, list) or len(value) != 2:
        raise _error(f"{field} must be [level, move]")
    level, move = value
    if not isinstance(level, int) or isinstance(level, bool) or level < 0:
        raise _error(f"{field}[0] must be a non-negative integer")
    if not isinstance(move, str) or not move.startswith("MOVE_") or len(move) <= len("MOVE_"):
        raise _error(f"{field}[1] must be a MOVE_* token")
    return level, move


def _parse_change(value: Any, index: int) -> LedgerChange:
    field = f"changes[{index}]"
    if not isinstance(value, dict):
        raise _error(f"{field} must be an object")

    species = value.get("species")
    if not isinstance(species, str) or not species:
        raise _error(f"{field}.species must be a species identifier")
    species = species.casefold()
    if not _IDENTIFIER_RE.fullmatch(species):
        raise _error(f"{field}.species contains unsupported path characters")

    operation = value.get("operation")
    if operation not in _SUPPORTED_OPERATIONS:
        raise _error(f"{field}.operation is unsupported")

    digest = value.get("source_sha256")
    if digest is not None:
        if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest.casefold()):
            raise _error(f"{field}.source_sha256 must be a 64-character SHA-256 digest")
        digest = digest.casefold()

    before: tuple[int, str] | None = None
    after: tuple[int, str] | None = None
    if operation == "insert_level_move":
        after = _parse_entry(value.get("entry"), f"{field}.entry")
    elif operation == "replace_level_move":
        before = _parse_entry(value.get("from"), f"{field}.from")
        after = _parse_entry(value.get("to"), f"{field}.to")
    else:
        before = _parse_entry(value.get("entry"), f"{field}.entry")

    return LedgerChange(
        species=species,
        operation=operation,
        before=before,
        after=after,
        source_sha256=digest,
    )


def load_ledger(path: Path) -> PokemonLedger:
    """Parse and validate a versioned Pokémon edit ledger."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _error(f"could not read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise _error("root must be an object")
    if data.get("version") != 1:
        raise _error("version must be 1")
    if data.get("domain") != "pokemon":
        raise _error("domain must be 'pokemon'")
    raw_changes = data.get("changes")
    if not isinstance(raw_changes, list) or not raw_changes:
        raise _error("changes must be a non-empty array")

    return PokemonLedger(
        version=1,
        domain="pokemon",
        changes=tuple(_parse_change(value, index) for index, value in enumerate(raw_changes)),
    )


def _learnset(data: dict[str, Any], relative_path: Path) -> list[list[Any]]:
    learnset = data.get("learnset")
    if not isinstance(learnset, dict):
        raise RomModError(f"{relative_path.as_posix()}: learnset is missing or malformed")
    by_level = learnset.get("by_level")
    if not isinstance(by_level, list):
        raise RomModError(f"{relative_path.as_posix()}: learnset.by_level is missing or malformed")
    for index, entry in enumerate(by_level):
        if (
            not isinstance(entry, list)
            or len(entry) != 2
            or not isinstance(entry[0], int)
            or isinstance(entry[0], bool)
            or entry[0] < 0
            or not isinstance(entry[1], str)
        ):
            raise RomModError(
                f"{relative_path.as_posix()}: learnset.by_level[{index}] is malformed"
            )
    return by_level


def _matching_indices(entries: list[list[Any]], expected: tuple[int, str]) -> list[int]:
    return [index for index, entry in enumerate(entries) if tuple(entry) == expected]


def _apply_change(entries: list[list[Any]], change: LedgerChange, relative_path: Path) -> None:
    if change.operation == "insert_level_move":
        assert change.after is not None
        if _matching_indices(entries, change.after):
            raise RomModError(
                f"{relative_path.as_posix()}: learnset already contains {list(change.after)!r}"
            )
        entries.append([change.after[0], change.after[1]])
        return

    assert change.before is not None
    matches = _matching_indices(entries, change.before)
    if len(matches) != 1:
        raise RomModError(
            f"{relative_path.as_posix()}: expected learnset entry {list(change.before)!r} "
            f"exactly once, found {len(matches)}"
        )

    index = matches[0]
    if change.operation == "remove_level_move":
        del entries[index]
        return

    assert change.after is not None
    if change.after != change.before and _matching_indices(entries, change.after):
        raise RomModError(
            f"{relative_path.as_posix()}: learnset already contains replacement {list(change.after)!r}"
        )
    entries[index] = [change.after[0], change.after[1]]


def _serialized_sha256(data: dict[str, Any], indent: int) -> str:
    raw = (json.dumps(data, indent=indent, ensure_ascii=False) + "\n").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _prepare_ledger(root: Path, ledger: PokemonLedger) -> tuple[_PreparedFile, ...]:
    if ledger.version != 1 or ledger.domain != "pokemon":
        raise _error("unsupported ledger version or domain")

    resolved_root = root.resolve()
    grouped: dict[str, list[LedgerChange]] = {}
    for change in ledger.changes:
        grouped.setdefault(change.species, []).append(change)

    prepared: list[_PreparedFile] = []
    for species in sorted(grouped):
        changes = grouped[species]
        source_path = resolved_root / "res" / "pokemon" / species / "data.json"
        if not source_path.is_file():
            raise RomModError(f"species source not found: res/pokemon/{species}/data.json")
        document = load_json_document(resolved_root, source_path)

        expected_digests = {change.source_sha256 for change in changes if change.source_sha256 is not None}
        if len(expected_digests) > 1:
            raise SourceMismatchError(
                f"{document.relative_path.as_posix()}: ledger contains conflicting source SHA-256 values"
            )
        if expected_digests and document.sha256 not in expected_digests:
            raise SourceMismatchError(
                f"{document.relative_path.as_posix()} ({species}) does not match ledger source SHA-256"
            )

        new_data = copy.deepcopy(document.data)
        entries = _learnset(new_data, document.relative_path)
        planned_changes: list[PlannedChange] = []
        for change in changes:
            _apply_change(entries, change, document.relative_path)
            planned_changes.append(
                PlannedChange(
                    species=change.species,
                    operation=change.operation,
                    before=change.before,
                    after=change.after,
                )
            )

        entries.sort(key=lambda entry: entry[0])
        planned = PlannedFile(
            source_path=document.relative_path,
            source_sha256=document.sha256,
            result_sha256=_serialized_sha256(new_data, document.indent),
            changes=tuple(planned_changes),
        )
        prepared.append(_PreparedFile(document=document, new_data=new_data, planned=planned))

    return tuple(prepared)


def plan_ledger(root: Path, ledger: PokemonLedger) -> LedgerPlan:
    """Validate all ledger edits and return a read-only deterministic plan."""

    prepared = _prepare_ledger(root, ledger)
    return LedgerPlan(files=tuple(item.planned for item in prepared), applied=False)


def apply_ledger(root: Path, ledger: PokemonLedger) -> LedgerPlan:
    """Preflight every ledger edit, then apply guarded atomic writes per source file."""

    unpinned = [change.species for change in ledger.changes if change.source_sha256 is None]
    if unpinned:
        species = ", ".join(sorted(set(unpinned)))
        raise SourceMismatchError(
            f"source_sha256 is required to apply ledger changes; unpinned species: {species}"
        )

    prepared = _prepare_ledger(root, ledger)
    snapshot = RepositorySnapshot(root)
    written: list[PlannedFile] = []
    for item in prepared:
        digest = write_json_document(snapshot, item.document, item.new_data)
        planned = item.planned
        if digest != planned.result_sha256:
            raise SourceMismatchError(
                f"{planned.source_path.as_posix()}: written digest differs from planned digest"
            )
        written.append(planned)
    return LedgerPlan(files=tuple(written), applied=True)
