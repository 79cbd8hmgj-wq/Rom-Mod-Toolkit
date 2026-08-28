from pathlib import Path

import pytest

from tests.fixtures.synthetic_nds import write_synthetic_nds


@pytest.fixture
def synthetic_rom_path(tmp_path: Path) -> Path:
    return write_synthetic_nds(tmp_path / "synthetic.nds")
