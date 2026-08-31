from __future__ import annotations

from pathlib import Path

from rommod.platforms.nds.free_space import discover_project_caves
from rommod.platforms.nds.rom import NdsRom
from rommod.projects.project import init_project
from tests.fixtures.synthetic_nds import make_synthetic_nds


def test_discover_project_caves_maps_offsets_to_cpu_addresses(tmp_path: Path):
    source = tmp_path / "game.nds"
    rom = NdsRom.from_bytes(make_synthetic_nds())
    rom._nds.arm9 = (
        (b"\x11" * 8)
        + (b"\x00" * 24)
        + (b"\x22" * 8)
        + (b"\x00" * 24)
    )
    source.write_bytes(rom.serialize())

    project = tmp_path / "mod"
    init_project(source, project)

    report = discover_project_caves(
        project,
        "arm9",
        min_size=16,
        fill=0x00,
        alignment=4,
    )

    assert report.target == "arm9"
    assert report.ram_address == 0x02000000
    assert report.target_size == 64
    assert [(item.offset, item.address, item.size, item.trailing) for item in report.candidates] == [
        (8, 0x02000008, 24, False),
        (40, 0x02000028, 24, True),
    ]
