"""Semantic diffs for normalized Pokémon source repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rommod.domains.pokemon.loader import load_repository_index
from rommod.domains.pokemon.models import RepositoryIndex, SpeciesRecord


_STAT_NAMES = (
    "hp",
    "attack",
    "defense",
    "special_attack",
    "special_defense",
    "speed",
)


@dataclass(frozen=True)
class StatChange:
    stat: str
    before: int
    after: int

    def to_dict(self) -> dict[str, object]:
        return {"stat": self.stat, "before": self.before, "after": self.after}


@dataclass(frozen=True)
class LearnsetChange:
    move: str
    kind: str
    before_level: int | None
    after_level: int | None

    def to_dict(self) -> dict[str, object]:
        return {
            "move": self.move,
            "kind": self.kind,
            "before_level": self.before_level,
            "after_level": self.after_level,
        }


@dataclass(frozen=True)
class SpeciesDiff:
    species: str
    display_name: str
    stats: tuple[StatChange, ...]
    bst_before: int
    bst_after: int
    learnset: tuple[LearnsetChange, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "species": self.species,
            "display_name": self.display_name,
            "stats": [change.to_dict() for change in self.stats],
            "bst": (
                {"before": self.bst_before, "after": self.bst_after}
                if self.bst_before != self.bst_after
                else None
            ),
            "learnset": [change.to_dict() for change in self.learnset],
        }


@dataclass(frozen=True)
class RepositoryDiff:
    before_root: Path
    after_root: Path
    species: tuple[SpeciesDiff, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": "pokemon",
            "before_root": str(self.before_root),
            "after_root": str(self.after_root),
            "changed_species": len(self.species),
            "species": [change.to_dict() for change in self.species],
        }


def _diff_stats(before: SpeciesRecord, after: SpeciesRecord) -> tuple[StatChange, ...]:
    changes: list[StatChange] = []
    for name, old_value, new_value in zip(
        _STAT_NAMES,
        before.base_stats,
        after.base_stats,
        strict=True,
    ):
        if old_value != new_value:
            changes.append(StatChange(name, old_value, new_value))
    return tuple(changes)


def _diff_learnset(before: SpeciesRecord, after: SpeciesRecord) -> tuple[LearnsetChange, ...]:
    before_levels = {entry.move: entry.level for entry in before.level_up_moves}
    after_levels = {entry.move: entry.level for entry in after.level_up_moves}
    changes: list[LearnsetChange] = []
    for move in sorted(set(before_levels) | set(after_levels)):
        old_level = before_levels.get(move)
        new_level = after_levels.get(move)
        if old_level == new_level:
            continue
        if old_level is None:
            kind = "added"
        elif new_level is None:
            kind = "removed"
        else:
            kind = "level"
        changes.append(LearnsetChange(move, kind, old_level, new_level))
    return tuple(changes)


def _diff_species(before: SpeciesRecord, after: SpeciesRecord) -> SpeciesDiff | None:
    stats = _diff_stats(before, after)
    learnset = _diff_learnset(before, after)
    if not stats and not learnset:
        return None
    return SpeciesDiff(
        species=after.identifier,
        display_name=after.display_name,
        stats=stats,
        bst_before=sum(before.base_stats),
        bst_after=sum(after.base_stats),
        learnset=learnset,
    )


def diff_indexes(before: RepositoryIndex, after: RepositoryIndex) -> RepositoryDiff:
    """Return deterministic semantic changes for species present in both indexes."""

    changes: list[SpeciesDiff] = []
    for identifier in sorted(set(before.species) & set(after.species)):
        change = _diff_species(before.species[identifier], after.species[identifier])
        if change is not None:
            changes.append(change)
    return RepositoryDiff(before.root, after.root, tuple(changes))


def diff_repositories(before_root: Path, after_root: Path) -> RepositoryDiff:
    """Load two source repositories and compare their normalized Pokémon data."""

    return diff_indexes(
        load_repository_index(before_root),
        load_repository_index(after_root),
    )
