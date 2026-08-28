"""NDS ROM facade around ndspy."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path

from ndspy.rom import NintendoDSRom

from rommod.errors import RomValidationError
from rommod.platforms.nds.metadata import NdsMetadata
from rommod.platforms.nds.validation import validate_nds_bytes


class NdsRom:
    def __init__(self, backend: NintendoDSRom, source_bytes: bytes):
        self._backend = backend
        self._source_bytes = bytes(source_bytes)

    @classmethod
    def load(cls, path: Path) -> "NdsRom":
        source = Path(path).read_bytes()
        return cls.from_bytes(source)

    @classmethod
    def from_bytes(cls, data: bytes) -> "NdsRom":
        source = bytes(data)
        validate_nds_bytes(source)
        try:
            backend = NintendoDSRom(source)
        except (AssertionError, ValueError, struct.error, IndexError) as exc:
            raise RomValidationError(f"ndspy could not parse NDS image: {exc}") from exc
        return cls(backend, source)

    def serialize(self) -> bytes:
        try:
            return self._backend.save()
        except (AssertionError, ValueError, struct.error, IndexError) as exc:
            raise RomValidationError(f"ndspy could not serialize NDS image: {exc}") from exc

    def metadata(self) -> NdsMetadata:
        data = self._source_bytes
        arm9 = struct.unpack_from("<4I", data, 0x20)
        arm7 = struct.unpack_from("<4I", data, 0x30)
        tables = struct.unpack_from("<8I", data, 0x40)
        banner_offset = struct.unpack_from("<I", data, 0x68)[0]
        return NdsMetadata(
            title=data[0:12].rstrip(b"\0").decode("ascii", "replace"),
            game_code=data[0x0C:0x10].decode("ascii", "replace"),
            maker_code=data[0x10:0x12].decode("ascii", "replace"),
            rom_version=data[0x1E],
            arm9_rom_offset=arm9[0],
            arm9_entry_address=arm9[1],
            arm9_ram_address=arm9[2],
            arm9_size=arm9[3],
            arm7_rom_offset=arm7[0],
            arm7_entry_address=arm7[1],
            arm7_ram_address=arm7[2],
            arm7_size=arm7[3],
            fnt_offset=tables[0],
            fnt_size=tables[1],
            fat_offset=tables[2],
            fat_size=tables[3],
            arm9_overlay_offset=tables[4],
            arm9_overlay_size=tables[5],
            arm7_overlay_offset=tables[6],
            arm7_overlay_size=tables[7],
            banner_offset=banner_offset,
            source_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )

    @property
    def _nds(self) -> NintendoDSRom:
        """Internal backend access for NDS adapter modules only."""
        return self._backend
