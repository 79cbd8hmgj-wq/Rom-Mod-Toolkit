"""Integrity validation for normalized Pokémon source repositories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rommod.domains.pokemon.loader import load_repository_index
from rommod.domains.pokemon.models import RepositoryIndex


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    species: str
    message: str
    source_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "species": self.species,
            "message": self.message,
            "source_path": str(self.source_path) if self.source_path is not None else None,
        }


@dataclass(frozen=True)
class SourceValidationReport:
    root: Path
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict[str, object]:
        return {
            "domain": "pokemon",
            "root": str(self.root),
            "valid": self.valid,
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _move_identifier(value: str) -> str:
    return value.removeprefix("MOVE_").casefold()


def _validate_species(index: RepositoryIndex) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    has_move_metadata = bool(index.moves)

    for identifier in sorted(index.species):
        species = index.species[identifier]
        seen_moves: set[str] = set()
        duplicate_moves: set[str] = set()

        for entry in species.level_up_moves:
            if entry.level > 100:
                issues.append(
                    ValidationIssue(
                        code="invalid-level",
                        species=identifier,
                        message=f"{entry.move} is learned at impossible level {entry.level}",
                        source_path=species.source_path,
                    )
                )

            if entry.move in seen_moves and entry.move not in duplicate_moves:
                duplicate_moves.add(entry.move)
                issues.append(
                    ValidationIssue(
                        code="duplicate-learnset-move",
                        species=identifier,
                        message=f"{entry.move} appears more than once in the level-up learnset",
                        source_path=species.source_path,
                    )
                )
            seen_moves.add(entry.move)

            if has_move_metadata and _move_identifier(entry.move) not in index.moves:
                issues.append(
                    ValidationIssue(
                        code="unknown-move",
                        species=identifier,
                        message=f"{entry.move} does not resolve to discovered move metadata",
                        source_path=species.source_path,
                    )
                )

    return issues


def _validate_evolutions(index: RepositoryIndex) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for evolution in sorted(
        index.evolutions,
        key=lambda item: (item.source, item.target, item.method, item.level or -1),
    ):
        source = index.species.get(evolution.source)
        source_path = source.source_path if source is not None else None
        if evolution.target not in index.species:
            issues.append(
                ValidationIssue(
                    code="broken-evolution",
                    species=evolution.source,
                    message=f"evolution target {evolution.target} does not exist in the repository",
                    source_path=source_path,
                )
            )
        if evolution.level is not None and evolution.level > 100:
            issues.append(
                ValidationIssue(
                    code="invalid-level",
                    species=evolution.source,
                    message=f"evolution to {evolution.target} uses impossible level {evolution.level}",
                    source_path=source_path,
                )
            )
    return issues


def validate_index(index: RepositoryIndex) -> SourceValidationReport:
    """Validate cross-record integrity in an already loaded Pokémon index."""

    issues = _validate_species(index) + _validate_evolutions(index)
    issues.sort(key=lambda issue: (issue.species, issue.code, issue.message))
    return SourceValidationReport(index.root, tuple(issues))


def validate_repository(root: Path) -> SourceValidationReport:
    """Load and validate a Pokémon source repository."""

    return validate_index(load_repository_index(root))
