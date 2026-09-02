from __future__ import annotations

from pathlib import Path

from rommod.domains.pokemon.analysis import analyze_repository
from rommod.domains.pokemon.models import (
    EvolutionRecord,
    LearnsetEntry,
    MoveRecord,
    RepositoryIndex,
    SpeciesRecord,
)


def _species(
    identifier: str,
    *,
    types: tuple[str, ...],
    learnset: tuple[LearnsetEntry, ...],
) -> SpeciesRecord:
    return SpeciesRecord(
        identifier=identifier,
        display_name=identifier.upper(),
        source_path=Path(f"res/pokemon/{identifier}/data.json"),
        types=types,
        base_stats=(60, 60, 60, 60, 60, 60),
        abilities=("ABILITY_NONE", "ABILITY_NONE"),
        level_up_moves=learnset,
    )


def _move(
    identifier: str,
    *,
    move_type: str,
    category: str,
    power: int,
) -> MoveRecord:
    return MoveRecord(
        identifier=identifier,
        display_name=identifier.replace("_", " ").title(),
        move_type=move_type,
        category=category,
        power=power,
        accuracy=100,
        pp=20,
        source_path=Path(f"res/moves/{identifier}/data.json"),
    )


def test_analyzer_flags_level_one_only_status_move() -> None:
    index = RepositoryIndex(
        root=Path("/repo"),
        species={
            "persian": _species(
                "persian",
                types=("TYPE_NORMAL", "TYPE_NORMAL"),
                learnset=(
                    LearnsetEntry(1, "MOVE_SWITCHEROO"),
                    LearnsetEntry(6, "MOVE_BITE"),
                ),
            )
        },
        moves={
            "switcheroo": _move(
                "switcheroo",
                move_type="TYPE_DARK",
                category="CLASS_STATUS",
                power=0,
            ),
            "bite": _move(
                "bite",
                move_type="TYPE_DARK",
                category="CLASS_PHYSICAL",
                power=60,
            ),
        },
    )

    findings = analyze_repository(index)

    finding = next(item for item in findings if item.code == "level-one-only-status")
    assert finding.species == "persian"
    assert finding.move == "switcheroo"
    assert finding.observed_level == 1
    assert finding.source_path == Path("res/pokemon/persian/data.json")


def test_analyzer_flags_post_evolution_stab_gap_and_nonstab_evolution_move() -> None:
    index = RepositoryIndex(
        root=Path("/repo"),
        species={
            "mankey": _species(
                "mankey",
                types=("TYPE_FIGHTING", "TYPE_FIGHTING"),
                learnset=(LearnsetEntry(25, "MOVE_ASSURANCE"),),
            ),
            "primeape": _species(
                "primeape",
                types=("TYPE_FIGHTING", "TYPE_FIGHTING"),
                learnset=(
                    LearnsetEntry(28, "MOVE_RAGE"),
                    LearnsetEntry(35, "MOVE_SWAGGER"),
                    LearnsetEntry(41, "MOVE_CROSS_CHOP"),
                ),
            ),
        },
        moves={
            "rage": _move(
                "rage",
                move_type="TYPE_NORMAL",
                category="CLASS_PHYSICAL",
                power=20,
            ),
            "swagger": _move(
                "swagger",
                move_type="TYPE_NORMAL",
                category="CLASS_STATUS",
                power=0,
            ),
            "cross_chop": _move(
                "cross_chop",
                move_type="TYPE_FIGHTING",
                category="CLASS_PHYSICAL",
                power=100,
            ),
        },
        evolutions=(EvolutionRecord("mankey", "primeape", "EVO_LEVEL", 28),),
    )

    findings = analyze_repository(index)

    gap = next(item for item in findings if item.code == "post-evolution-stab-gap")
    assert gap.species == "primeape"
    assert gap.evolution_from == "mankey"
    assert gap.evolution_level == 28
    assert gap.move == "cross_chop"
    assert gap.observed_level == 41
    assert gap.gap_levels == 13

    payoff = next(item for item in findings if item.code == "evolution-level-non-stab")
    assert payoff.species == "primeape"
    assert payoff.move == "rage"
    assert payoff.evolution_level == 28


def test_analyzer_flags_moves_delayed_by_evolving() -> None:
    index = RepositoryIndex(
        root=Path("/repo"),
        species={
            "ponyta": _species(
                "ponyta",
                types=("TYPE_FIRE", "TYPE_FIRE"),
                learnset=(
                    LearnsetEntry(42, "MOVE_BOUNCE"),
                    LearnsetEntry(46, "MOVE_FLARE_BLITZ"),
                ),
            ),
            "rapidash": _species(
                "rapidash",
                types=("TYPE_FIRE", "TYPE_FIRE"),
                learnset=(
                    LearnsetEntry(40, "MOVE_FURY_ATTACK"),
                    LearnsetEntry(47, "MOVE_BOUNCE"),
                    LearnsetEntry(56, "MOVE_FLARE_BLITZ"),
                ),
            ),
        },
        moves={},
        evolutions=(EvolutionRecord("ponyta", "rapidash", "EVO_LEVEL", 40),),
    )

    findings = analyze_repository(index)
    delays = [item for item in findings if item.code == "evolution-move-delay"]

    assert [(item.move, item.gap_levels) for item in delays] == [
        ("bounce", 5),
        ("flare_blitz", 10),
    ]
    assert all(item.species == "rapidash" for item in delays)
    assert all(item.evolution_from == "ponyta" for item in delays)
