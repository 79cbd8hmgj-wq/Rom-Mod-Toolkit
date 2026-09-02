from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def test_build_cli_dispatches_make_based_source_projects(tmp_path: Path, capsys) -> None:
    pokemon = tmp_path / "res" / "pokemon" / "pikachu"
    moves = tmp_path / "res" / "moves" / "tackle"
    pokemon.mkdir(parents=True)
    moves.mkdir(parents=True)
    (pokemon / "data.json").write_text(
        json.dumps({"learnset": {"by_level": []}, "evolutions": []}) + "\n",
        encoding="utf-8",
    )
    (moves / "data.json").write_text(json.dumps({"name": "Tackle"}) + "\n", encoding="utf-8")
    (tmp_path / "Makefile").write_text(
        "all:\n\tmkdir -p build\n\tprintf 'NDS' > build/game.nds\n",
        encoding="utf-8",
    )

    exit_code = main(["build", str(tmp_path)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "source"
    assert output["build_system"] == "make"
    assert output["outputs"] == ["build/game.nds"]
    assert output["report"].endswith("rommod/reports/build.json")
