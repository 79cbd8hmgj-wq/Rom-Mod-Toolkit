from __future__ import annotations

import json
from pathlib import Path

from rommod.cli import main


def test_scan_cli_emits_json_and_writes_discovery_reports(tmp_path: Path, capsys) -> None:
    (tmp_path / "Makefile").write_text("CC=arm-none-eabi-gcc\n", encoding="utf-8")
    pokemon = tmp_path / "res" / "pokemon" / "pikachu"
    moves = tmp_path / "res" / "moves" / "tackle"
    pokemon.mkdir(parents=True)
    moves.mkdir(parents=True)
    (pokemon / "data.json").write_text(
        json.dumps({"learnset": {"by_level": []}, "evolutions": []}) + "\n",
        encoding="utf-8",
    )
    (moves / "data.json").write_text(json.dumps({"name": "Tackle"}) + "\n", encoding="utf-8")

    exit_code = main(["scan", str(tmp_path)])

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["platform"] == "nds"
    assert output["project_type"] == "pokemon_decomp"
    assert output["build_system"] == "make"
    assert output["toolchains"] == ["arm-none-eabi"]
    assert (tmp_path / "rommod" / "project.json").is_file()
    assert (tmp_path / "rommod" / "reports" / "project_scan.json").is_file()
