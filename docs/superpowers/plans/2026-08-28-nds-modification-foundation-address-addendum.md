# NDS Modification Foundation — Address Mapping Addendum

This addendum is a required part of `2026-08-28-nds-modification-foundation.md`. It closes the only spec-coverage gap found during plan self-review: Section 8 of the approved design requires deterministic CPU-address/file-offset handling with fail-closed behavior.

## Task 5A: Typed NDS address mapping

**Files:**
- Create: `src/rommod/platforms/nds/addresses.py`
- Create: `tests/unit/test_addresses.py`

**Interfaces:**

```python
from dataclasses import dataclass

@dataclass(frozen=True, order=True)
class CpuAddress:
    value: int

@dataclass(frozen=True, order=True)
class FileOffset:
    value: int

@dataclass(frozen=True)
class AddressRegion:
    target: str
    ram_address: CpuAddress
    file_size: int


def cpu_to_file_offset(region: AddressRegion, address: CpuAddress) -> FileOffset: ...
def file_offset_to_cpu(region: AddressRegion, offset: FileOffset) -> CpuAddress: ...
```

### Required behavior

- CPU addresses and file offsets must never be accepted interchangeably by type-aware APIs.
- Mapping is valid only for a region where loaded bytes and serialized target bytes have a direct 1:1 mapping.
- ARM9/ARM7 regions use their declared RAM base and serialized binary size when the target is not code-compressed.
- Overlay regions use overlay RAM base and raw file size only when the overlay is not compressed.
- Compressed ARM binaries or overlays must raise `AddressResolutionError` in this Phase 1 mapper rather than guessing at an offset.
- Addresses below the region RAM base or beyond the mapped file-sized region raise `AddressResolutionError`.
- File offsets below zero or >= file size raise `AddressResolutionError`.
- Later decoded-code/armips work may add a separate loaded-image mapping; it must not change the raw-file semantics of Phase 1 `byte_patch`.

- [ ] **Step 1: Write failing tests**

```python
import pytest
from rommod.errors import AddressResolutionError
from rommod.platforms.nds.addresses import (
    AddressRegion,
    CpuAddress,
    FileOffset,
    cpu_to_file_offset,
    file_offset_to_cpu,
)


def test_cpu_address_maps_to_file_offset():
    region = AddressRegion("arm9", CpuAddress(0x02000000), 0x100)
    assert cpu_to_file_offset(region, CpuAddress(0x02000020)) == FileOffset(0x20)


def test_file_offset_maps_to_cpu_address():
    region = AddressRegion("overlay9:3", CpuAddress(0x02100000), 0x80)
    assert file_offset_to_cpu(region, FileOffset(0x10)) == CpuAddress(0x02100010)


def test_cpu_address_outside_region_fails_closed():
    region = AddressRegion("arm7", CpuAddress(0x03800000), 0x40)
    with pytest.raises(AddressResolutionError):
        cpu_to_file_offset(region, CpuAddress(0x037FFFFC))
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/unit/test_addresses.py -v`
Expected: import failure because the mapper does not exist yet.

- [ ] **Step 3: Implement minimal mapper**

```python
def cpu_to_file_offset(region: AddressRegion, address: CpuAddress) -> FileOffset:
    delta = address.value - region.ram_address.value
    if delta < 0 or delta >= region.file_size:
        raise AddressResolutionError(
            f"CPU address 0x{address.value:08X} is outside {region.target}"
        )
    return FileOffset(delta)


def file_offset_to_cpu(region: AddressRegion, offset: FileOffset) -> CpuAddress:
    if offset.value < 0 or offset.value >= region.file_size:
        raise AddressResolutionError(
            f"file offset 0x{offset.value:X} is outside {region.target}"
        )
    return CpuAddress(region.ram_address.value + offset.value)
```

Target-specific region factories must check compression before constructing an `AddressRegion`. Overlay compression comes from `ndspy.code.Overlay.compressed`. For ARM7/ARM9, compare `ndspy.codeCompression.decompress(raw)` to the raw target; if it differs, treat the target as compressed and reject raw address mapping.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_addresses.py -v`
Expected: PASS.

- [ ] **Step 5: Add target-region tests**

Using the synthetic NDS fixture, assert uncompressed ARM9 and the uncompressed synthetic overlay produce correct regions. Add a deliberately code-compressed target fixture or monkeypatched compressed-detection case and assert `AddressResolutionError`.

- [ ] **Step 6: Run relevant suite**

Run: `pytest tests/unit/test_addresses.py tests/integration/test_nds_roundtrip.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/rommod/platforms/nds/addresses.py tests/unit/test_addresses.py
git commit -m "feat: add typed NDS address mapping"
```

## Plan ordering

Execute this addendum immediately after Task 5 (ARM binaries/overlays/extraction) and before Task 6 (guarded byte patches). It introduces no new CLI command; it establishes the safe address abstraction required by later armips/symbol-aware phases.