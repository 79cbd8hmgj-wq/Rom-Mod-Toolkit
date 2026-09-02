from __future__ import annotations

import json
from pathlib import Path

from rommod.dev.checkpoints import compare_checkpoints, create_checkpoint, restore_checkpoint


def _write(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _species(attack: int, flare_blitz_level: int) -> dict[str, object]:
    return {
        "base_stats": {
            "hp": 80,
            "attack": attack,
            "defense": 130,
            "special_attack": 45,
            "special_defense": 80,
            "speed": 45,
        },
        "types": ["TYPE_ROCK", "TYPE_GROUND"],
        "abilities": ["ABILITY_ROCK_HEAD"],
        "learnset": {"by_level": [[flare_blitz_level, "MOVE_FLARE_BLITZ"]]},
        "evolutions": [],
        "pokedex_data": {"en": {"name": "GOLEM"}},
    }


def _seed(root: Path, attack: int, flare_blitz_level: int) -> None:
    _write(root / "res" / "pokemon" / "golem" / "data.json", _species(attack, flare_blitz_level))
    _write(
        root / "res" / "moves" / "flare_blitz" / "data.json",
        {
            "name": "Flare Blitz",
            "type": "TYPE_FIRE",
            "class": "CLASS_PHYSICAL",
            "power": 120,
            "accuracy": 100,
            "pp": 15,
        },
    )


def test_checkpoint_captures_hashes_build_report_and_source_snapshot(tmp_path: Path) -> None:
    _seed(tmp_path, 120, 56)
    _write(tmp_path / "rommod" / "reports" / "build.json", {"success": True})

    checkpoint = create_checkpoint(tmp_path, "C3D2 Block 1B")

    assert checkpoint.directory.name == "C3D2_Block_1B"
    assert (checkpoint.directory / "metadata.json").is_file()
    assert (checkpoint.directory / "hashes.json").is_file()
    assert (checkpoint.directory / "changes.json").is_file()
    assert (checkpoint.directory / "diff.html").is_file()
    assert json.loads((checkpoint.directory / "build.json").read_text()) == {"success": True}
    snap = checkpoint.directory / "source" / "res" / "pokemon" / "golem" / "data.json"
    assert json.loads(snap.read_text())["base_stats"]["attack"] == 120


def test_checkpoints_compare_semantically_and_restore_guarded_snapshot(tmp_path: Path) -> None:
    _seed(tmp_path, 120, 56)
    first = create_checkpoint(tmp_path, "before")

    _seed(tmp_path, 130, 46)
    second = create_checkpoint(tmp_path, "after")

    diff = compare_checkpoints(first.directory, second.directory).to_dict()
    assert diff["changed_species"] == 1
    assert diff["species"][0]["stats"] == [{"stat": "attack", "before": 120, "after": 130}]
    assert diff["species"][0]["learnset"][0] == {
        "move": "MOVE_FLARE_BLITZ",
        "kind": "level",
        "before_level": 56,
        "after_level": 46,
    }

    restored = restore_checkpoint(tmp_path, first.directory)
    current = json.loads((tmp_path / "res" / "pokemon" / "golem" / "data.json").read_text())
    assert restored.restored_files == 2
    assert current["base_stats"]["attack"] == 120
    assert current["learnset"]["by_level"] == [[56, "MOVE_FLARE_BLITZ"]]
