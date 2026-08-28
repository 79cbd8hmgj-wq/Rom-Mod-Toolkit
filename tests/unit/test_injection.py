from __future__ import annotations

import pytest

from rommod.errors import BuildError, ExternalToolError
from rommod.platforms.nds.injection import find_trailing_fill_cave, validate_injection_fragment


def test_find_trailing_fill_cave_uses_start_of_aligned_trailing_run():
    data = bytes(range(1, 65)) + b"\x00" * 64
    cave = find_trailing_fill_cave(data, reserve=16, fill=0, alignment=4)
    assert cave.value == 64


def test_find_trailing_fill_cave_rejects_non_trailing_internal_run():
    data = b"\x11" * 16 + b"\x00" * 64 + b"\x22" * 4
    with pytest.raises(BuildError, match="trailing"):
        find_trailing_fill_cave(data, reserve=16, fill=0, alignment=4)


@pytest.mark.parametrize("source", [".org 0x02000040", ".orga 0x40", ".thumb", ".arm", "__rommod_payload_0000:"])
def test_injection_fragment_rejects_position_mode_and_reserved_labels(source: str):
    with pytest.raises(ExternalToolError, match="injection"):
        validate_injection_fragment(source)
