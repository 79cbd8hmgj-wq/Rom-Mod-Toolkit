# NDS Modification Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working Nintendo DS path for Rom Mod Toolkit: project initialization, source locking, ROM inspection/extraction, guarded modifications, deterministic rebuild, and structural verification.

**Architecture:** A small platform-neutral Python core owns project manifests, hashing, paths, errors, and build orchestration. The NDS adapter wraps `ndspy` 4.2.0 behind toolkit-owned models and never exposes mutable `ndspy` objects as the public API. Phase 1 always rebuilds from the verified source ROM plus declared mutations; advanced armips/code-injection functionality remains the immediate follow-up slice.

**Tech Stack:** Python 3.10+, `ndspy==4.2.0`, PyYAML, `pytest`, standard-library `argparse`, `hashlib`, `json`, `pathlib`, and `tempfile`.

**Spec:** `docs/superpowers/specs/2026-08-28-nds-modification-foundation-design.md`

## Global Constraints

- NDS is the first production platform path; PSP-specific requirements must not affect Phase 1.
- Never modify the user's source ROM in place.
- Every initialized project records and enforces the source ROM SHA-256.
- Build starts from the verified source ROM plus declared mutations, not from stale extracted files.
- Every exact byte patch requires expected original bytes and fails closed on mismatch.
- CPU addresses and target-relative file offsets are distinct concepts.
- NitroFS Phase 1 supports replacement of existing files only; create/delete is deferred.
- A failed build must not leave a partially-written configured output ROM.
- Rebuilt output must parse through a fresh NDS loader and requested mutations must be verified.
- Tests must not require proprietary commercial ROM data.
- Armips, patch generation, Keystone, Unicorn, code-cave discovery, hooks/trampolines, compiled C injection, symbol-aware patching, and PSP support are outside this first implementation slice.
- `ndspy` source reviewed for this plan is version 4.2.0 and requires Python >=3.8; this toolkit will target Python >=3.10.
- `ndspy.rom.NintendoDSRom.save()` repacks ROM regions, recalculates FAT offsets/header values, aligns sections, and may therefore produce a structurally equivalent rather than byte-identical untouched rebuild.

---

## File Map

```text
Rom-Mod-Toolkit/
├── pyproject.toml                         # package metadata, dependencies, CLI entry point
├── README.md                              # Phase 1 scope and basic commands
├── src/rommod/
│   ├── __init__.py                        # package version/export surface
│   ├── cli.py                             # argparse command routing only
│   ├── errors.py                          # typed RomModError hierarchy
│   ├── core/
│   │   ├── __init__.py
│   │   ├── hashes.py                      # streaming SHA-256
│   │   ├── paths.py                       # project-relative containment
│   │   └── atomic.py                      # atomic binary/text writes
│   ├── projects/
│   │   ├── __init__.py
│   │   ├── manifest.py                    # manifest dataclasses + YAML codec
│   │   ├── project.py                     # init/load project operations
│   │   └── build.py                       # ordered Phase 1 build pipeline + report
│   └── platforms/
│       ├── __init__.py
│       └── nds/
│           ├── __init__.py
│           ├── metadata.py                # normalized immutable metadata models
│           ├── validation.py              # source/rebuild structural checks
│           ├── rom.py                     # NdsRom facade around NintendoDSRom
│           ├── filesystem.py              # NitroFS enumerate/extract/replace
│           ├── binaries.py                # ARM9/ARM7 raw target access
│           ├── overlays.py                # overlay metadata/raw target access
│           ├── bytepatch.py               # guarded target-relative patching
│           └── extract.py                 # project extraction report/materialization
├── tests/
│   ├── fixtures/
│   │   └── synthetic_nds.py               # programmatic redistributable fixture
│   ├── unit/
│   │   ├── test_hashes.py
│   │   ├── test_paths.py
│   │   ├── test_manifest.py
│   │   ├── test_bytepatch.py
│   │   └── test_metadata.py
│   └── integration/
│       ├── test_project_init.py
│       ├── test_nds_roundtrip.py
│       ├── test_extract.py
│       ├── test_build_file_replace.py
│       └── test_build_bytepatch.py
└── docs/superpowers/...
```

---

### Task 1: Package shell, errors, hashing, paths, and atomic writes

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/rommod/__init__.py`
- Create: `src/rommod/cli.py`
- Create: `src/rommod/errors.py`
- Create: `src/rommod/core/__init__.py`
- Create: `src/rommod/core/hashes.py`
- Create: `src/rommod/core/paths.py`
- Create: `src/rommod/core/atomic.py`
- Test: `tests/unit/test_hashes.py`
- Test: `tests/unit/test_paths.py`

**Interfaces:**
- Produces: `sha256_file(path: Path) -> str`
- Produces: `resolve_inside(root: Path, relative: str | Path) -> Path`
- Produces: `atomic_write_bytes(path: Path, data: bytes) -> None`
- Produces: typed exceptions rooted at `RomModError`

- [ ] **Step 1: Write failing hash/path tests**

```python
from pathlib import Path
import pytest

from rommod.core.hashes import sha256_file
from rommod.core.paths import resolve_inside
from rommod.errors import ManifestError


def test_sha256_file(tmp_path: Path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_resolve_inside_rejects_escape(tmp_path: Path):
    with pytest.raises(ManifestError):
        resolve_inside(tmp_path, "../escape.bin")
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/unit/test_hashes.py tests/unit/test_paths.py -v`
Expected: import/module failures because package shell does not exist.

- [ ] **Step 3: Implement minimal core and packaging**

`pyproject.toml` must include:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "rom-mod-toolkit"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["ndspy==4.2.0", "PyYAML>=6.0"]

[project.optional-dependencies]
test = ["pytest>=8"]

[project.scripts]
rommod = "rommod.cli:main"
```

`errors.py` must define:

```python
class RomModError(Exception): pass
class ManifestError(RomModError): pass
class SourceMismatchError(RomModError): pass
class RomValidationError(RomModError): pass
class TargetNotFoundError(RomModError): pass
class PatchMismatchError(RomModError): pass
class AddressResolutionError(RomModError): pass
class ExternalToolError(RomModError): pass
class BuildError(RomModError): pass
```

`resolve_inside()` must resolve the root and candidate and reject candidates that are not equal to or descendants of root.

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_hashes.py tests/unit/test_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src tests/unit/test_hashes.py tests/unit/test_paths.py
git commit -m "feat: scaffold ROM mod toolkit core"
```

---

### Task 2: Manifest model and source-locked project initialization

**Files:**
- Create: `src/rommod/projects/__init__.py`
- Create: `src/rommod/projects/manifest.py`
- Create: `src/rommod/projects/project.py`
- Modify: `src/rommod/cli.py`
- Test: `tests/unit/test_manifest.py`
- Test: `tests/integration/test_project_init.py`

**Interfaces:**
- Consumes: `sha256_file`, `resolve_inside`, `ManifestError`, `SourceMismatchError`
- Produces: `SourceConfig`, `OutputConfig`, `FileReplaceChange`, `BytePatchChange`, `ProjectManifest`
- Produces: `load_manifest(project_dir: Path) -> ProjectManifest`
- Produces: `write_manifest(project_dir: Path, manifest: ProjectManifest) -> None`
- Produces: `init_project(source_rom: Path, project_dir: Path) -> ProjectManifest`
- Produces: `verify_source(project_dir: Path, manifest: ProjectManifest) -> Path`

- [ ] **Step 1: Write failing manifest and init tests**

```python
def test_manifest_round_trip(tmp_path):
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom="../game.nds", sha256="a" * 64),
        output=OutputConfig(rom="build/output/game-modded.nds"),
        changes=(),
    )
    write_manifest(tmp_path, manifest)
    assert load_manifest(tmp_path) == manifest


def test_init_locks_source_hash(tmp_path, synthetic_rom_path):
    project = tmp_path / "mod"
    manifest = init_project(synthetic_rom_path, project)
    assert manifest.platform == "nds"
    assert manifest.source.sha256 == sha256_file(synthetic_rom_path)
    assert (project / "rommod.yaml").is_file()
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/unit/test_manifest.py tests/integration/test_project_init.py -v`
Expected: missing project-model symbols.

- [ ] **Step 3: Implement strict YAML parsing**

Use frozen dataclasses. Unknown `schema_version`, unknown `platform`, unknown change `type`, malformed hex byte strings, or missing required keys must raise `ManifestError` with the field path.

Initial YAML form:

```yaml
schema_version: 1
platform: nds
source:
  rom: ../game.nds
  sha256: <64 lowercase hex chars>
output:
  rom: build/output/game-modded.nds
changes: []
```

`init_project()` creates `patches/`, `asm/`, `files/`, `build/extracted/`, `build/work/`, `build/output/`, and `reports/`, but does not copy or mutate the source ROM.

- [ ] **Step 4: Wire `rommod init`**

CLI parsing:

```python
init_parser.add_argument("source", type=Path)
init_parser.add_argument("project", type=Path)
```

CLI calls `init_project()` and prints the project path plus source SHA-256.

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_manifest.py tests/integration/test_project_init.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/rommod/projects src/rommod/cli.py tests/unit/test_manifest.py tests/integration/test_project_init.py
git commit -m "feat: add source-locked project manifests"
```

---

### Task 3: Synthetic NDS fixture and normalized ROM inspection

**Files:**
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/synthetic_nds.py`
- Create: `tests/conftest.py`
- Create: `src/rommod/platforms/__init__.py`
- Create: `src/rommod/platforms/nds/__init__.py`
- Create: `src/rommod/platforms/nds/metadata.py`
- Create: `src/rommod/platforms/nds/validation.py`
- Create: `src/rommod/platforms/nds/rom.py`
- Modify: `src/rommod/cli.py`
- Test: `tests/unit/test_metadata.py`
- Test: `tests/integration/test_nds_roundtrip.py`

**Interfaces:**
- Consumes: `ndspy.rom.NintendoDSRom.fromFile()`, `.save()`
- Produces: immutable `NdsMetadata`
- Produces: `NdsRom.load(path: Path) -> NdsRom`
- Produces: `NdsRom.metadata() -> NdsMetadata`
- Produces: `NdsRom.serialize() -> bytes`
- Produces: `validate_nds_bytes(data: bytes) -> None`

- [ ] **Step 1: Create a redistributable synthetic fixture generator**

Construct a `NintendoDSRom()` in memory, set deterministic identity/header fields, ARM9/ARM7 byte sequences, a small filename table, and at least one NitroFS file. Save with `NintendoDSRom.save()` and expose a pytest fixture `synthetic_rom_path`.

Do not embed Nintendo logo/trademark data copied from a commercial ROM; use only what `ndspy` itself creates by default or synthetic bytes acceptable to its serializer/parser.

- [ ] **Step 2: Write failing inspection/roundtrip tests**

```python
def test_load_metadata(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    meta = rom.metadata()
    assert meta.game_code == "TST1"
    assert meta.arm9_size > 0
    assert meta.arm7_size > 0


def test_untouched_save_reloads(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    rebuilt = NdsRom.from_bytes(rom.serialize())
    assert rebuilt.metadata().game_code == rom.metadata().game_code
```

- [ ] **Step 3: Run tests and verify failure**

Run: `pytest tests/unit/test_metadata.py tests/integration/test_nds_roundtrip.py -v`
Expected: missing NDS facade.

- [ ] **Step 4: Implement validation + metadata normalization**

Normalize at minimum:

```python
@dataclass(frozen=True)
class NdsMetadata:
    title: str
    game_code: str
    maker_code: str
    rom_version: int
    arm9_rom_offset: int
    arm9_entry_address: int
    arm9_ram_address: int
    arm9_size: int
    arm7_rom_offset: int
    arm7_entry_address: int
    arm7_ram_address: int
    arm7_size: int
    fnt_offset: int
    fnt_size: int
    fat_offset: int
    fat_size: int
    arm9_overlay_offset: int
    arm9_overlay_size: int
    arm7_overlay_offset: int
    arm7_overlay_size: int
    banner_offset: int
    source_size: int
    sha256: str
```

`validate_nds_bytes()` checks minimum header length and that declared ARM9/ARM7/FNT/FAT/overlay ranges fit inside the image. Convert low-level `ValueError`, `struct.error`, or serializer failures into `RomValidationError`.

- [ ] **Step 5: Add `rommod inspect`**

For a ROM path, print normalized JSON. For a project path, first verify the source hash, then inspect the configured source.

- [ ] **Step 6: Run tests**

Run: `pytest tests/unit/test_metadata.py tests/integration/test_nds_roundtrip.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/rommod/platforms tests/fixtures tests/conftest.py tests/unit/test_metadata.py tests/integration/test_nds_roundtrip.py src/rommod/cli.py
git commit -m "feat: add NDS loading inspection and validation"
```

---

### Task 4: NitroFS enumeration, extraction, and replacement

**Files:**
- Create: `src/rommod/platforms/nds/filesystem.py`
- Test: `tests/integration/test_extract.py`
- Test: `tests/integration/test_build_file_replace.py`

**Interfaces:**
- Consumes: `NintendoDSRom.filenames.filenameOf(file_id)`, `.files`, `.getFileByName()`, `.setFileByName()`
- Produces: `NdsFileEntry(path: str, file_id: int, size: int)`
- Produces: `list_files(rom: NdsRom) -> tuple[NdsFileEntry, ...]`
- Produces: `extract_files(rom: NdsRom, destination: Path) -> list[Path]`
- Produces: `replace_file(rom: NdsRom, target: str, data: bytes) -> None`

- [ ] **Step 1: Write failing NitroFS tests**

```python
def test_lists_named_nitrofs_file(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    assert any(e.path == "data/example.bin" for e in list_files(rom))


def test_replace_existing_file_roundtrip(synthetic_rom_path):
    rom = NdsRom.load(synthetic_rom_path)
    replace_file(rom, "data/example.bin", b"changed")
    rebuilt = NdsRom.from_bytes(rom.serialize())
    assert rebuilt.backend.getFileByName("data/example.bin") == b"changed"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/integration/test_extract.py tests/integration/test_build_file_replace.py -v`
Expected: missing filesystem functions.

- [ ] **Step 3: Implement enumeration without assuming folders are iterable**

The uploaded `ndspy.fnt.Folder` explicitly raises from `__iter__`; enumerate by file ID over `rom.backend.files` and call `rom.backend.filenames.filenameOf(file_id)`. Ignore unnamed IDs during path extraction but preserve them in the ROM backend.

`replace_file()` must normalize leading `/`, require an existing named file, and translate `ndspy`'s missing-file `ValueError` into `TargetNotFoundError`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/test_extract.py tests/integration/test_build_file_replace.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/rommod/platforms/nds/filesystem.py tests/integration/test_extract.py tests/integration/test_build_file_replace.py
git commit -m "feat: add NDS NitroFS access"
```

---

### Task 5: ARM binaries, overlay metadata, and extraction snapshot

**Files:**
- Create: `src/rommod/platforms/nds/binaries.py`
- Create: `src/rommod/platforms/nds/overlays.py`
- Create: `src/rommod/platforms/nds/extract.py`
- Modify: `src/rommod/cli.py`
- Expand: `tests/integration/test_extract.py`

**Interfaces:**
- Produces: `get_main_binary(rom: NdsRom, processor: Literal["arm9", "arm7"]) -> bytes`
- Produces: `set_main_binary(...) -> None`
- Produces: `NdsOverlayInfo`
- Produces: `list_overlays(rom: NdsRom, processor: Literal["arm9", "arm7"]) -> tuple[NdsOverlayInfo, ...]`
- Produces: `get_overlay_raw(rom: NdsRom, processor: str, overlay_id: int) -> bytes`
- Produces: `set_overlay_raw(...) -> None`
- Produces: `extract_project(project_dir: Path) -> dict`

- [ ] **Step 1: Extend synthetic fixture with one ARM9 overlay**

Use `ndspy.code.Overlay` plus `saveOverlayTable()` to create one deterministic overlay whose file ID points into `rom.files`.

- [ ] **Step 2: Write failing extraction assertions**

`rommod extract` must produce:

```text
build/extracted/metadata.json
build/extracted/arm9.bin
build/extracted/arm7.bin
build/extracted/overlays/arm9/0.bin
build/extracted/overlays/arm9/index.json
build/extracted/nitrofs/data/example.bin
reports/source.json
```

Overlay index JSON records processor, overlay ID, RAM address, RAM size, BSS size, static initializer start/end, file ID, compressed size, flags, and `compressed`.

- [ ] **Step 3: Implement raw target access**

For Phase 1 exact byte-patch semantics, ARM9/ARM7 and overlay target bytes are the **serialized/raw bytes stored in the ROM**, because manifest offsets are defined as target-relative file offsets. Overlay metadata may be parsed through `loadArm9Overlays()` / `loadArm7Overlays()`, but `get_overlay_raw()` reads `rom.backend.files[overlay.fileID]` directly.

This intentionally avoids conflating compressed serialized offsets with decompressed CPU-memory offsets. Later armips/address-aware phases will introduce a separate decoded-code target abstraction.

- [ ] **Step 4: Implement extraction + `rommod extract`**

Extraction is inspection output only. It must clear/recreate `build/extracted` deterministically and write JSON with sorted keys + stable indentation.

- [ ] **Step 5: Run extraction tests**

Run: `pytest tests/integration/test_extract.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/rommod/platforms/nds/binaries.py src/rommod/platforms/nds/overlays.py src/rommod/platforms/nds/extract.py src/rommod/cli.py tests
git commit -m "feat: extract NDS binaries overlays and NitroFS"
```

---

### Task 6: Guarded exact byte patches

**Files:**
- Create: `src/rommod/platforms/nds/bytepatch.py`
- Test: `tests/unit/test_bytepatch.py`
- Expand: `tests/integration/test_build_bytepatch.py`

**Interfaces:**
- Consumes: main/overlay raw-target access and NitroFS access
- Produces: `apply_guarded_patch(data: bytes, offset: int, expected: bytes, replacement: bytes) -> bytes`
- Produces: `apply_byte_change(rom: NdsRom, change: BytePatchChange) -> None`

- [ ] **Step 1: Write failing unit tests**

```python
def test_guarded_patch_replaces_expected_bytes():
    assert apply_guarded_patch(b"abcdef", 2, b"cd", b"XY") == b"abXYef"


def test_guarded_patch_rejects_mismatch():
    with pytest.raises(PatchMismatchError):
        apply_guarded_patch(b"abcdef", 2, b"zz", b"XY")


def test_guarded_patch_rejects_out_of_range():
    with pytest.raises(PatchMismatchError):
        apply_guarded_patch(b"abc", 3, b"d", b"X")
```

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/unit/test_bytepatch.py -v`
Expected: missing patch functions.

- [ ] **Step 3: Implement target routing**

Supported targets:

```text
arm9
arm7
overlay9:<decimal-id>
overlay7:<decimal-id>
file:<NitroFS/path>
```

Require `len(expected) == len(replacement)` in Phase 1 so exact byte patches cannot resize executables or files. A size-changing file edit uses `file_replace`, not `byte_patch`.

- [ ] **Step 4: Add integration tests for ARM9 and overlay patching**

Build/reload and assert modified raw target bytes are present. Add a mismatched-expected test that verifies build failure and absence of the final output file.

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/test_bytepatch.py tests/integration/test_build_bytepatch.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/rommod/platforms/nds/bytepatch.py tests/unit/test_bytepatch.py tests/integration/test_build_bytepatch.py
git commit -m "feat: add guarded NDS byte patches"
```

---

### Task 7: Ordered build pipeline, atomic output, and build report

**Files:**
- Create: `src/rommod/projects/build.py`
- Modify: `src/rommod/cli.py`
- Expand: `tests/integration/test_build_file_replace.py`
- Expand: `tests/integration/test_build_bytepatch.py`

**Interfaces:**
- Produces: `BuildResult(output_path: Path, source_sha256: str, output_sha256: str, report_path: Path)`
- Produces: `build_project(project_dir: Path) -> BuildResult`

- [ ] **Step 1: Write failing end-to-end build tests**

A manifest containing a file replacement followed by a byte patch must apply changes in declared order, rebuild, validate, and write `reports/build.json`.

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/integration/test_build_file_replace.py tests/integration/test_build_bytepatch.py -v`
Expected: no build orchestration.

- [ ] **Step 3: Implement build stages exactly**

```python
def build_project(project_dir: Path) -> BuildResult:
    manifest = load_manifest(project_dir)
    source = verify_source(project_dir, manifest)
    rom = NdsRom.load(source)
    prepare_clean_work_dir(project_dir)
    for change in manifest.changes:
        apply_change(rom, project_dir, change)
    output_bytes = rom.serialize()
    validate_nds_bytes(output_bytes)
    verify_declared_changes(NdsRom.from_bytes(output_bytes), project_dir, manifest)
    atomic_write_bytes(output_path, output_bytes)
    write_build_report(...)
    return BuildResult(...)
```

The actual implementation may factor helpers, but stage order must remain visible/testable.

Report JSON must include:

```json
{
  "schema_version": 1,
  "platform": "nds",
  "source_sha256": "...",
  "output_sha256": "...",
  "output_size": 1234,
  "changes": [],
  "validation": {"parse_reload": true, "declared_changes": true},
  "tools": {"ndspy": "4.2.0"}
}
```

- [ ] **Step 4: Wire `rommod build`**

CLI errors derived from `RomModError` print a concise diagnostic to stderr and exit non-zero without a traceback unless a future debug flag is added.

- [ ] **Step 5: Run integration tests twice for determinism**

Run: `pytest tests/integration/test_build_file_replace.py tests/integration/test_build_bytepatch.py -v`
Expected: PASS and same output SHA-256 for two identical builds from the same source and manifest.

- [ ] **Step 6: Commit**

```bash
git add src/rommod/projects/build.py src/rommod/cli.py tests/integration
git commit -m "feat: add deterministic NDS build pipeline"
```

---

### Task 8: Standalone/project verification command and corruption tests

**Files:**
- Expand: `src/rommod/platforms/nds/validation.py`
- Modify: `src/rommod/cli.py`
- Create: `tests/integration/test_verify.py`

**Interfaces:**
- Produces: `VerificationReport(valid: bool, metadata: NdsMetadata, checks: tuple[str, ...])`
- Produces: `verify_rom(path: Path) -> VerificationReport`
- Produces: `verify_project(project_dir: Path) -> VerificationReport`

- [ ] **Step 1: Write failing verification tests**

Test valid synthetic ROM, truncated ARM9 range, malformed FAT range, valid project output, and project output missing on disk.

- [ ] **Step 2: Run and verify failure**

Run: `pytest tests/integration/test_verify.py -v`
Expected: missing verification API/CLI.

- [ ] **Step 3: Implement structural checks**

At minimum verify:

- header is present;
- ARM9 range in bounds;
- ARM7 range in bounds;
- FNT range in bounds;
- FAT range in bounds and length divisible by 8;
- overlay table lengths divisible by 32;
- each FAT entry start <= end <= ROM length;
- each overlay table file ID is within FAT/file count;
- fresh `NintendoDSRom` parse succeeds.

- [ ] **Step 4: Wire `rommod verify`**

A file argument verifies the file. A directory argument loads its manifest and verifies configured output after verifying source identity.

- [ ] **Step 5: Run tests**

Run: `pytest tests/integration/test_verify.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/rommod/platforms/nds/validation.py src/rommod/cli.py tests/integration/test_verify.py
git commit -m "feat: add NDS structural verification"
```

---

### Task 9: CLI contract, documentation, and full Phase 1 gate

**Files:**
- Modify: `README.md`
- Modify: `src/rommod/cli.py`
- Create: `tests/integration/test_cli.py`

**Interfaces:**
- Final Phase 1 commands:
  - `rommod init <game.nds> <project-dir>`
  - `rommod inspect <game.nds-or-project>`
  - `rommod extract <project-dir>`
  - `rommod build <project-dir>`
  - `rommod verify <game.nds-or-project>`

`rommod patch` is documented as the next slice, not exposed as a fake/stub command.

- [ ] **Step 1: Write CLI smoke tests**

Use `subprocess.run([sys.executable, "-m", "rommod.cli", ...])` or install the editable package in the test environment. Verify exit code 0 for valid flows and non-zero for source-hash mismatch and patch mismatch.

- [ ] **Step 2: Run and verify current behavior**

Run: `pytest tests/integration/test_cli.py -v`
Expected: failures for any missing command contract/error translation.

- [ ] **Step 3: Finish CLI and README**

README must explain:

- NDS-only Phase 1 scope;
- source ROMs are never modified in place;
- manifests lock SHA-256;
- exact byte patches are guarded by expected bytes;
- extracted files are inspection/authoring artifacts, not implicit build inputs;
- untouched rebuilt ROMs may not be byte-identical because `ndspy` repacks layout;
- no commercial ROMs are shipped with the project;
- armips/patch-generation are the next development slice.

- [ ] **Step 4: Run the complete suite**

Run: `pytest -v`
Expected: all tests PASS, no optional-tool skips because this slice has no required external binaries.

- [ ] **Step 5: Run CLI smoke sequence manually against synthetic fixture**

```bash
rommod init /tmp/synthetic.nds /tmp/test-mod
rommod inspect /tmp/test-mod
rommod extract /tmp/test-mod
rommod build /tmp/test-mod
rommod verify /tmp/test-mod
```

Expected: all five commands exit 0; output ROM exists; source SHA-256 is unchanged.

- [ ] **Step 6: Commit**

```bash
git add README.md src/rommod/cli.py tests/integration/test_cli.py
git commit -m "docs: complete NDS foundation milestone"
```

---

## Phase 1 Completion Gate

Before declaring this plan complete, verify all of the following:

```bash
pytest -v
python -m rommod.cli --help
```

Required evidence:

- package imports on Python 3.10+;
- project initialization writes a SHA-256-locked manifest;
- changing the source ROM after initialization causes `SourceMismatchError`;
- NDS metadata inspection is read-only;
- extraction exports ARM9, ARM7, overlays, NitroFS, and metadata;
- NitroFS replacement rebuilds and reloads correctly;
- ARM9 guarded byte patch rebuilds and reloads correctly;
- overlay guarded byte patch rebuilds and reloads correctly;
- expected-byte mismatch aborts without replacing configured output;
- build output parses via a fresh `NintendoDSRom` instance;
- two identical builds produce the same output SHA-256;
- `verify` catches deliberately corrupt header/FAT/overlay ranges;
- source ROM SHA-256 before and after all operations is identical;
- test suite contains no commercial ROM data.

## Immediate Follow-up Plan

After this gate passes, create a separate implementation plan for the next NDS slice:

1. armips executable discovery/version reporting;
2. decoded ARM9/ARM7/overlay working targets;
3. explicit ARM vs Thumb assembly jobs;
4. CPU-address-aware patch mapping;
5. armips symbol output capture;
6. BPS/IPS generation through Flips;
7. xdelta generation;
8. only then begin symbol-aware hooks/code injection.

Do not start PSP implementation before that NDS modification path is proven.