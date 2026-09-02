"""Semantic Pokémon source analysis built on normalized repository records."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rommod.domains.pokemon.models import EvolutionRecord, MoveRecord, RepositoryIndex, SpeciesRecord


@dataclass(frozen=True)
class PokemonFinding:
    """One deterministic, source-backed Pokémon design finding."""

    code: str
    species: str
    message: str
    source_path: Path | None = None
    move: str | None = None
    evolution_from: str | None = None
    evolution_level: int | None = None
    observed_level: int | None = None
    gap_levels: int | None = None


def _move_identifier(token: str) -> str:
    if token.startswith("MOVE_"):
        token = token.removeprefix("MOVE_")
    return token.casefold()


def _move_record(index: RepositoryIndex, token: str) -> MoveRecord | None:
    return index.moves.get(_move_identifier(token))


def _is_damaging_stab(index: RepositoryIndex, species: SpeciesRecord, token: str) -> bool:
    move = _move_record(index, token)
    if move is None or move.power is None or move.power <= 0 or move.move_type is None:
        return False
    return move.move_type in species.types


def _level_one_only_status_findings(index: RepositoryIndex) -> list[PokemonFinding]:
    findings: list[PokemonFinding] = []
    for species in index.species.values():
        levels_by_move: dict[str, list[int]] = {}
        token_by_move: dict[str, str] = {}
        for entry in species.level_up_moves:
            identifier = _move_identifier(entry.move)
            levels_by_move.setdefault(identifier, []).append(entry.level)
            token_by_move[identifier] = entry.move

        for identifier, levels in levels_by_move.items():
            if not levels or any(level != 1 for level in levels):
                continue
            move = _move_record(index, token_by_move[identifier])
            if move is None or move.category != "CLASS_STATUS":
                continue
            findings.append(
                PokemonFinding(
                    code="level-one-only-status",
                    species=species.identifier,
                    move=identifier,
                    observed_level=1,
                    source_path=species.source_path,
                    message=(
                        f"{species.display_name} only learns {move.display_name} at level 1; "
                        "normal level progression never reaches it."
                    ),
                )
            )
    return findings


def _level_map_after(species: SpeciesRecord, minimum_level: int) -> dict[str, int]:
    levels: dict[str, int] = {}
    for entry in species.level_up_moves:
        if entry.level < minimum_level:
            continue
        identifier = _move_identifier(entry.move)
        current = levels.get(identifier)
        if current is None or entry.level < current:
            levels[identifier] = entry.level
    return levels


def _evolution_findings(index: RepositoryIndex, evolution: EvolutionRecord) -> list[PokemonFinding]:
    if evolution.level is None:
        return []
    source = index.species.get(evolution.source)
    target = index.species.get(evolution.target)
    if source is None or target is None:
        return []

    findings: list[PokemonFinding] = []
    evolution_level = evolution.level

    exact_moves = [entry for entry in target.level_up_moves if entry.level == evolution_level]
    for entry in exact_moves:
        if _is_damaging_stab(index, target, entry.move):
            continue
        identifier = _move_identifier(entry.move)
        move = _move_record(index, entry.move)
        display_name = move.display_name if move is not None else identifier
        findings.append(
            PokemonFinding(
                code="evolution-level-non-stab",
                species=target.identifier,
                move=identifier,
                evolution_from=source.identifier,
                evolution_level=evolution_level,
                observed_level=evolution_level,
                source_path=target.source_path,
                message=(
                    f"{target.display_name} receives {display_name} at its level-{evolution_level} "
                    "evolution point, but that move is not a damaging same-type payoff."
                ),
            )
        )

    next_stab = next(
        (
            entry
            for entry in target.level_up_moves
            if entry.level >= evolution_level and _is_damaging_stab(index, target, entry.move)
        ),
        None,
    )
    if next_stab is not None and next_stab.level > evolution_level:
        identifier = _move_identifier(next_stab.move)
        gap = next_stab.level - evolution_level
        move = _move_record(index, next_stab.move)
        display_name = move.display_name if move is not None else identifier
        findings.append(
            PokemonFinding(
                code="post-evolution-stab-gap",
                species=target.identifier,
                move=identifier,
                evolution_from=source.identifier,
                evolution_level=evolution_level,
                observed_level=next_stab.level,
                gap_levels=gap,
                source_path=target.source_path,
                message=(
                    f"{target.display_name} evolves at level {evolution_level} but its next damaging "
                    f"same-type level-up move, {display_name}, arrives {gap} levels later."
                ),
            )
        )

    source_levels = _level_map_after(source, evolution_level)
    target_levels = _level_map_after(target, evolution_level)
    for move_identifier, source_level in source_levels.items():
        target_level = target_levels.get(move_identifier)
        if target_level is None or target_level <= source_level:
            continue
        gap = target_level - source_level
        findings.append(
            PokemonFinding(
                code="evolution-move-delay",
                species=target.identifier,
                move=move_identifier,
                evolution_from=source.identifier,
                evolution_level=evolution_level,
                observed_level=target_level,
                gap_levels=gap,
                source_path=target.source_path,
                message=(
                    f"Evolving {source.display_name} into {target.display_name} delays "
                    f"{move_identifier.replace('_', ' ').title()} from level {source_level} "
                    f"to level {target_level} ({gap} levels)."
                ),
            )
        )

    return findings


def analyze_repository(index: RepositoryIndex) -> tuple[PokemonFinding, ...]:
    """Return deterministic source-backed design findings for a Pokémon decomp."""

    findings = _level_one_only_status_findings(index)
    for evolution in index.evolutions:
        findings.extend(_evolution_findings(index, evolution))

    return tuple(
        sorted(
            findings,
            key=lambda item: (
                item.species,
                item.code,
                item.move or "",
                item.evolution_from or "",
                item.observed_level if item.observed_level is not None else -1,
            ),
        )
    )
