import pytest

from rommod.errors import PatchMismatchError
from rommod.platforms.nds.bytepatch import apply_guarded_patch


def test_guarded_patch_replaces_expected_bytes():
    assert apply_guarded_patch(b"abcdef", 2, b"cd", b"XY") == b"abXYef"


def test_guarded_patch_rejects_mismatch():
    with pytest.raises(PatchMismatchError, match="expected bytes"):
        apply_guarded_patch(b"abcdef", 2, b"zz", b"XY")


def test_guarded_patch_rejects_out_of_range():
    with pytest.raises(PatchMismatchError, match="outside target"):
        apply_guarded_patch(b"abc", 3, b"d", b"X")


def test_guarded_patch_rejects_size_change():
    with pytest.raises(PatchMismatchError, match="same length"):
        apply_guarded_patch(b"abcdef", 2, b"cd", b"XYZ")
