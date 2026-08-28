from __future__ import annotations

import pytest

from rommod.errors import ExternalToolError
from rommod.platforms.nds.assembler import validate_armips_fragment


@pytest.mark.parametrize(
    "source",
    [
        '.open "other.bin",0x02000000',
        '.create "new.bin",0',
        '.close',
        '.include "other.asm"',
        '.incbin "other.bin"',
        '.import "other.bin"',
        '.importobj "other.o"',
        '.importlib "other.a"',
        '.relativeinclude on',
        '.headersize 0x10',
        '.nds',
        '.gba',
    ],
)
def test_fragment_rejects_file_ownership_and_architecture_directives(source: str):
    with pytest.raises(ExternalToolError, match="not allowed"):
        validate_armips_fragment(source)


def test_fragment_allows_arm_thumb_and_cpu_org():
    validate_armips_fragment(".thumb\n.org 0x02000010\nnop\n.arm\n")
