from __future__ import annotations

from pathlib import Path

from ndspy import code, fnt
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
    overlay = code.Overlay(
        bytes(range(0xA0, 0xB0)),
        ramAddress=0x02100000,
        ramSize=16,
        bssSize=4,
        staticInitStart=0x02100000,
        staticInitEnd=0x02100004,
        fileID=1,
        compressedSize=16,
        flags=0,
    )
    rom.arm9OverlayTable = code.saveOverlayTable({0: overlay})
    rom.files = [b"original-data", overlay.save(compress=False)]
    rom.sortedFileIds = [0, 1]
    return rom.save()


def write_synthetic_nds(path: Path) -> Path:
    path.write_bytes(make_synthetic_nds())
    return path
