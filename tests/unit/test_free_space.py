from __future__ import annotations

import pytest

from rommod.errors import BuildError
from rommod.platforms.nds.free_space import scan_fill_runs


def test_scan_fill_runs_reports_internal_and_trailing_candidates():
    data = b"\x11\x22" + (b"\x00" * 10) + b"\x33" + (b"\x00" * 12)

    candidates = scan_fill_runs(
        data,
        min_size=8,
        fill=0x00,
        alignment=4,
        base_address=0x02000000,
    )

    assert [(item.offset, item.address, item.size, item.trailing) for item in candidates] == [
        (4, 0x02000004, 8, False),
        (16, 0x02000010, 9, True),
    ]


def test_scan_fill_runs_applies_alignment_before_minimum_size():
    data = b"\xAA" + (b"\xFF" * 10) + b"\xBB"

    assert scan_fill_runs(
        data,
        min_size=9,
        fill=0xFF,
        alignment=4,
        base_address=0x02380000,
    ) == ()


def test_scan_fill_runs_rejects_invalid_configuration():
    with pytest.raises(BuildError, match="minimum size"):
        scan_fill_runs(b"\x00" * 8, min_size=0)
    with pytest.raises(BuildError, match="alignment"):
        scan_fill_runs(b"\x00" * 8, min_size=4, alignment=0)
    with pytest.raises(BuildError, match="fill"):
        scan_fill_runs(b"\x00" * 8, min_size=4, fill=256)
