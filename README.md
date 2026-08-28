# Rom Mod Toolkit

`Rom-Mod-Toolkit` is an NDS-first toolkit for reproducible ROM inspection, extraction, modification, rebuild, and verification.

The current NDS path combines a trustworthy Phase 1 rebuild foundation with Phase 2 armips-backed ARM/Thumb patching. A project always rebuilds from a SHA-256-locked source ROM plus declared mutations; the source ROM is never modified in place.

## Current NDS capabilities

- Initialize a Nintendo DS mod project and lock the source ROM by SHA-256.
- Inspect normalized NDS header, ARM9, ARM7, filesystem, and overlay metadata.
- Extract ARM9, ARM7, NitroFS files, and ARM9/ARM7 overlays for inspection.
- Replace existing NitroFS files.
- Apply exact, guarded byte patches to ARM9, ARM7, overlays, or NitroFS files.
- Rebuild through `ndspy` and reparse the output before it is accepted.
- Verify key header ranges, FAT entries, overlay-table references, and fresh parsing.
- Produce deterministic build output for the same source, manifest, and dependency versions.
- Write a machine-readable `reports/build.json` with source/output hashes and applied mutations.
- Keep CPU addresses and target-relative file offsets as separate typed concepts in the library.
- Run real `armips` fragments against isolated ARM9, ARM7, ARM9-overlay, or ARM7-overlay working copies.
- Permit ARM/Thumb mode switching and CPU-address `.org` patches without exposing the source ROM to armips.
- Emit optional armips symbol files only after rebuilt-ROM validation succeeds.
- Record the resolved armips executable and version in build reports when assembly patches are used.

## Requirements

- Python 3.10+
- `ndspy==4.2.0`
- `PyYAML>=6.0`
- `armips` 0.11-compatible executable when a project contains `type: armips` changes

For development/testing:

```bash
python -m pip install -e ".[test]"
pytest -q
```

## Command workflow

```bash
rommod init game.nds my-mod
rommod inspect my-mod
rommod extract my-mod
rommod build my-mod
rommod verify my-mod
```

You can also inspect or verify a standalone ROM:

```bash
rommod inspect game.nds
rommod verify game.nds
```

Toolkit validation errors are printed as concise `error: ...` diagnostics and return exit code `2`.

## Project layout

`rommod init` creates:

```text
my-mod/
├── rommod.yaml
├── asm/
├── files/
├── patches/
├── build/
│   ├── extracted/
│   ├── output/
│   └── work/
└── reports/
```

The configured source may live outside the project. Its SHA-256 is recorded in `rommod.yaml`; builds and project verification fail if that source changes.

## Manifest

Minimal project:

```yaml
schema_version: 1
platform: nds
source:
  rom: ../game.nds
  sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
output:
  rom: build/output/game-modded.nds
changes: []
```

### Replace an existing NitroFS file

Put the replacement inside the project and declare it:

```yaml
changes:
  - type: file_replace
    target: data/example.bin
    source: files/example.bin
```

Phase 1 only replaces existing NitroFS paths. Creating or deleting filesystem entries is intentionally deferred.

### Guarded byte patch

Every byte patch includes the bytes expected at the target location. If they do not match, the build aborts without writing the configured output.

```yaml
changes:
  - type: byte_patch
    target: arm9
    offset: 0x1234
    expected: "01 02 03 04"
    replacement: "AA BB CC DD"
```

Supported byte-patch targets:

```text
arm9
arm7
overlay9:<overlay-id>
overlay7:<overlay-id>
file:<nitrofs/path>
```

`offset` is always a target-relative serialized-file offset. It is **not** a CPU address.

### ARM/Thumb assembly patch

Assembly fragments run against an isolated copy of one code target under `build/work/armips/`; armips never receives the source ROM. Configure the executable explicitly, through `ROMMOD_ARMIPS`, or on `PATH`:

```yaml
tools:
  armips: /path/to/armips

changes:
  - type: armips
    target: arm9
    script: asm/battle_patch.asm
    symbols: reports/battle_patch.sym
```

Example fragment:

```asm
.org 0x02001234
.thumb
nop
.arm
PatchEnd:
```

Supported assembly targets are `arm9`, `arm7`, `overlay9:<id>`, and `overlay7:<id>`. The wrapper selects the appropriate ARM architecture and maps `.org` CPU addresses to the target's RAM base. A fragment may switch between `.arm` and `.thumb`.

For safety, the first armips slice rejects fragment directives that take ownership of files or architecture selection, including `.open`, `.create`, `.close`, `.include`, `.headersize`, `.nds`, and `.gba`. Patched targets must remain exactly the same serialized size. A missing or failed assembler aborts the build without writing the configured ROM output.

Tool resolution order is:

1. `tools.armips` in `rommod.yaml`;
2. `ROMMOD_ARMIPS`;
3. `armips` on `PATH`.

### Import analysis symbols into armips

An armips change can import the component-aware JSON emitted by the NDS analysis/disassembly workflow and use those names directly in assembly. Runtime address alone is not treated as unique because overlays can overlap in RAM; component identity remains part of symbol resolution.

```yaml
changes:
  - type: armips
    target: overlay9:0
    script: asm/battle_patch.asm
    symbol_file: analysis/symbols.json
    symbol_component: battle_overlay
```

Accepted symbol files are either a JSON array or an object with a `symbols` array. Each record carries at least `component`, runtime `address`, component-relative `offset`, and `name`; `instruction_set` may be `arm`, `thumb`, or null. ARM symbols become `.definearmlabel`, Thumb symbols become `.definethumblabel`, and neutral/data labels become `.definelabel`.

Before armips runs, every imported symbol is checked against the selected target's uncompressed RAM mapping. Address/offset mismatches, out-of-range symbols, unsafe identifiers, duplicate names, or missing requested components fail closed.

Example fragment using an imported symbol:

```asm
.org PatchSite
.word 0xAABBCCDD
```

### Automatic ARM hook injection

`type: inject` builds a guarded ARM hook from a named imported symbol, places the payload in reserved free space, and automatically branches back to the instruction after the overwritten hook. The first injector intentionally supports **ARM hooks only**; Thumb hooks are rejected until the veneer/trampoline layer is enabled.

```yaml
changes:
  - type: inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleDamage
    expected: "05 06 07 08"
    script: asm/battle_damage_payload.asm
    cave: auto
    reserve: 32
    fill: "00"
    symbols: reports/battle_damage.sym
```

The payload is a positionless ARM fragment; the toolkit owns `.org`, architecture/mode selection, the generated hook branch, the cave label, and the return branch. File-owning/import directives remain forbidden.

`cave: auto` searches only the **trailing** run of the requested fill byte in the selected target, aligned to four bytes. It never treats an arbitrary internal zero run as executable free space. An explicit cave may instead be supplied as a CPU address. The reserved cave must already contain exactly the declared fill byte.

After armips runs, the toolkit diffs the complete target and rejects any changed byte outside the 4-byte hook or declared cave reserve. The hook and cave cannot overlap, target size cannot change, and the configured ROM output is not written when any guard fails. Resolved hook/cave addresses are recorded in `reports/build.json`.

## Extraction output

`rommod extract my-mod` refreshes `build/extracted/` with a human-inspectable snapshot:

```text
build/extracted/
├── metadata.json
├── arm9.bin
├── arm7.bin
├── nitrofs/
└── overlays/
    ├── arm9/
    │   ├── index.json
    │   └── <id>.bin
    └── arm7/
        ├── index.json
        └── <id>.bin
```

Extraction is for inspection and authoring. Builds do **not** blindly rebuild from this directory; they start from the verified source ROM and apply only manifest-declared changes.

## Build safety

An NDS build performs this sequence:

1. Parse the project manifest.
2. Resolve the source ROM and verify its SHA-256.
3. Load and structurally validate the NDS image.
4. Clean the temporary build workspace.
5. Apply changes in manifest order.
6. Snapshot every touched target for post-rebuild verification.
7. Serialize the ROM through the NDS backend.
8. Validate the serialized image.
9. Reload it through a fresh NDS parser.
10. Confirm every touched target survived rebuild exactly.
11. Atomically write the output ROM.
12. Record hashes, mutations, validation state, and the `ndspy` version in `reports/build.json`.

A failed mutation or validation stage does not write a partial configured output.

## Verification scope

`rommod verify` currently checks:

- minimum NDS header size;
- ARM9 and ARM7 ranges;
- FNT/FAT and overlay-table ranges;
- FAT record alignment and entry bounds;
- ARM9/ARM7 overlay-table record alignment;
- overlay file IDs against the FAT;
- a fresh parse of the validated image.

This is structural verification, not proof that a game behaves correctly in an emulator.

## Rebuild equivalence

`ndspy` may repack regions, align sections, update FAT offsets, and recalculate header values when saving. Therefore an untouched rebuild is expected to be deterministic and structurally equivalent, but it is not universally required to be byte-for-byte identical to the source ROM.

## Tests

The test suite uses a programmatically generated synthetic Nintendo DS fixture; no proprietary commercial ROM is required.

```bash
pytest -q
```

Coverage includes project initialization, source mismatch rejection, load/save/reload, metadata normalization, NitroFS extraction/replacement, overlay access, address mapping, guarded patch failures, deterministic builds, structural corruption detection, the complete CLI workflow, armips manifest/tool resolution, fragment safety, component-aware symbol import, address/offset validation, real ARM9/ARM7/overlay assembly builds, and guarded automatic ARM hook injection when armips is available.

## Deferred NDS work

The current NDS path does **not** yet include:

- Thumb hooks and long-range veneers/trampolines;
- broader code-cave/free-space discovery beyond guarded trailing fill runs;
- compiled C/C++ injection and linking;
- Keystone or Unicorn integration;
- BPS/IPS/xdelta patch-file generation;
- NitroFS create/delete operations;
- emulator-driven behavioral validation.

The immediate next phase extends the proven ARM injector with Thumb-safe veneers/trampolines while preserving the same hook-byte, cave, and diff guards.

## PSP status

PSP source references are intentionally parked. PSP support will begin only after the NDS modification path is mature enough to establish the shared interfaces without forcing PSP-specific design into the NDS foundation.
