from __future__ import annotations

import json
from pathlib import Path

import pytest

from rommod.errors import ManifestError
from rommod.platforms.nds.symbols import ImportedSymbolTable, load_symbol_table


def _symbol(component: str, address: int, offset: int, name: str, instruction_set=None):
    return {
        "component": component,
        "address": address,
        "offset": offset,
        "name": name,
        "kind": "function",
        "instruction_set": instruction_set,
        "confidence": "high",
        "evidence": ["test"],
    }


def test_load_symbol_table_accepts_object_and_preserves_component_identity(tmp_path: Path):
    path = tmp_path / "symbols.json"
    path.write_text(
        json.dumps(
            {
                "symbols": [
                    _symbol("overlay9:1", 0x02100000, 0, "Shared", "arm"),
                    _symbol("overlay9:2", 0x02100000, 0, "Shared", "thumb"),
                ]
            }
        ),
        encoding="utf-8",
    )
    table = load_symbol_table(path)
    assert isinstance(table, ImportedSymbolTable)
    assert table.by_name("Shared", component="overlay9:1")[0].instruction_set == "arm"
    assert table.by_name("Shared", component="overlay9:2")[0].instruction_set == "thumb"
    assert len(table.by_name("Shared")) == 2


def test_load_symbol_table_accepts_raw_array(tmp_path: Path):
    path = tmp_path / "symbols.json"
    path.write_text(json.dumps([_symbol("arm9", 0x02000004, 4, "PatchSite", "arm")]), encoding="utf-8")
    table = load_symbol_table(path)
    assert table.for_component("arm9")[0].address == 0x02000004


@pytest.mark.parametrize(
    "record, message",
    [
        ({"component": "arm9"}, "address"),
        (_symbol("", 0x02000000, 0, "X"), "component"),
        (_symbol("arm9", -1, 0, "X"), "address"),
        (_symbol("arm9", 0x02000000, -1, "X"), "offset"),
        (_symbol("arm9", 0x02000000, 0, "", None), "name"),
        (_symbol("arm9", 0x02000000, 0, "X", "mips"), "instruction_set"),
    ],
)
def test_load_symbol_table_rejects_malformed_records(tmp_path: Path, record: dict, message: str):
    path = tmp_path / "symbols.json"
    path.write_text(json.dumps([record]), encoding="utf-8")
    with pytest.raises(ManifestError, match=message):
        load_symbol_table(path)
