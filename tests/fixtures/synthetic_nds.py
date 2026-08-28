from __future__ import annotations

from pathlib import Path

from ndspy import fnt
from ndspy.rom import NintendoDSRom


def make_synthetic_nds() -> bytes:
    rom = NintendoDSRom()
    rom.name = b"ROMMOD TEST"
    rom.idCode = b"TST1"
    rom.developerCode = b"RM"
    rom.version = 1
    rom.arm9EntryAddress = 0x02000000
    rom.arm9RamAddress = 0x02000000
    rom.arm7EntryAddress = 0x02380000
    rom.arm7RamAddress = 0x02380000
    rom.arm9 = bytes(range(1, 65))
    rom.arm7 = bytes(range(65, 97))
    rom.filenames = fnt.Folder(
        folders=[("data", fnt.Folder(files=["example.bin"], firstID=0))],
        files=[],
        firstID=0,
    )
    rom.files = [b"original-data"]
    rom.sortedFileIds = [0]
    return rom.save()


def write_synthetic_nds(path: Path) -> Path:
    path.write_bytes(make_synthetic_nds())
    return path
