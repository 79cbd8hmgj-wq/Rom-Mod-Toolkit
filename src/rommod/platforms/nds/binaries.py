"""Raw ARM9/ARM7 target access."""

from __future__ import annotations

from typing import Literal

from rommod.errors import TargetNotFoundError
from rommod.platforms.nds.rom import NdsRom

Processor = Literal["arm9", "arm7"]


def _validate_processor(processor: str) -> Processor:
    if processor not in ("arm9", "arm7"):
        raise TargetNotFoundError(f"Unknown NDS processor target: {processor}")
    return processor  # type: ignore[return-value]


def get_main_binary(rom: NdsRom, processor: Processor) -> bytes:
    processor = _validate_processor(processor)
    return bytes(rom._nds.arm9 if processor == "arm9" else rom._nds.arm7)


def set_main_binary(rom: NdsRom, processor: Processor, data: bytes) -> None:
    processor = _validate_processor(processor)
    if processor == "arm9":
        rom._nds.arm9 = bytes(data)
    else:
        rom._nds.arm7 = bytes(data)
