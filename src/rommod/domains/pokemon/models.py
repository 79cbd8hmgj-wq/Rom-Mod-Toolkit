"""Normalized immutable records for Pokémon repository data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, order=True)
class LearnsetEntry:
    level: int
    move: str


@dataclass(frozen=True)
class MoveRecord:
    identifier: str
    display_name: str
    move_type: str | None = None
    category: str | None = None
    power: int | None = None
    accuracy: int | None = None
    pp: int | None = None
    source_path: Path | None = None


@dataclass(frozen=True)
class EvolutionRecord:
    source: str
    target: str
    method: str
    level: int | None = None


@dataclass(frozen=True)
class SpeciesRecord:
    identifier: str
    display_name: str
    source_path: Path
    types: tuple[str, ...]
    base_stats: tuple[int, int, int, int, int, int]
    abilities: tuple[str, ...]
    level_up_moves: tuple[LearnsetEntry, ...]

    @property
    def hp(self) -> int:
        return self.base_stats[0]

    @property
    def attack(self) -> int:
        return self.base_stats[1]

    @property
    def defense(self) -> int:
        return self.base_stats[2]

    @property
    def special_attack(self) -> int:
        return self.base_stats[3]

    @property
    def special_defense(self) -> int:
        return self.base_stats[4]

    @property
    def speed(self) -> int:
        return self.base_stats[5]


@dataclass(frozen=True)
class RepositoryIndex:
    root: Path
    species: dict[str, SpeciesRecord]
    moves: dict[str, MoveRecord] = field(default_factory=dict)
    evolutions: tuple[EvolutionRecord, ...] = ()
    warnings: tuple[str, ...] = ()
