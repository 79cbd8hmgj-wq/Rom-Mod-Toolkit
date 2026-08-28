# Rom Mod Toolkit

`Rom-Mod-Toolkit` is an NDS-first toolkit for reproducible ROM inspection, extraction, modification, rebuild, and verification.

The toolkit prioritizes a trustworthy rebuild path. A project always rebuilds from a SHA-256-locked source ROM plus declared mutations; the source ROM is never modified in place.

## Current NDS capabilities

- Initialize a Nintendo DS mod project and lock the source ROM by SHA-256.
- Inspect normalized NDS header, ARM9, ARM7, filesystem, and overlay metadata.
- Extract ARM9, ARM7, NitroFS files, and ARM9/ARM7 overlays for inspection.
- Replace existing NitroFS files.
- Apply exact, guarded byte patches to ARM9, ARM7, overlays, or NitroFS files.
- Apply real ARM/Thumb assembly fragments through `armips` to ARM9, ARM7, ARM9 overlays, and ARM7 overlays.
- Optionally generate armips symbol files after a successful validated rebuild.
- Rebuild through `ndspy` and reparse the output before it is accepted.
- Verify key header ranges, FAT entries, overlay-table references, and fresh parsing.
- Produce deterministic build output for the same source, manifest, and dependency/tool versions.
- Write a machine-readable `reports/build.json` with source/output hashes, applied mutations, and external tool versions.
- Keep CPU addresses and target-relative file offsets as separate typed concepts in the library.

## Requirements

- Python 3.10+
- `ndspy==4.2.0`
- `PyYAML>=6.0`
- armips 0.11-compatible executable when assembly patches are used

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

```yaml
changes:
  - type: file_replace
    target: data/example.bin
    source: files/example.bin
```

The current filesystem mutation path replaces existing NitroFS paths. Creating or deleting entries is deferred.

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

## armips assembly patches

Assembly patches are declared as normal manifest changes. `armips` is resolved in this order:

1. `tools.armips` in `rommod.yaml`;
2. `ROMMOD_ARMIPS` environment variable;
3. system `PATH`.

Example configuration:

```yaml
tools:
  armips: tools/armips

changes:
  - type: armips
    target: arm9
    script: asm/battle_patch.asm
    symbols: reports/battle_patch.sym
```

The user script is an **assembly fragment**, not a complete armips project. The toolkit owns the target file, architecture declaration, open/close directives, build workspace, and final reinsertion into the ROM.

Example ARM9 fragment:

```asm
.org 0x02012340
.arm
mov r0, #1
bx lr
PatchEnd:
```

A fragment may switch between `.arm` and `.thumb`. `.org` uses CPU addresses. ARM9 and ARM9 overlays are wrapped using the NDS ARM architecture; ARM7 and ARM7 overlays are wrapped using ARM7-compatible settings. CPU-address mapping is rejected for compressed targets rather than guessed.

Supported armips targets:

```text
arm9
arm7
overlay9:<overlay-id>
overlay7:<overlay-id>
```

For safety, fragments cannot take ownership of files or architecture selection. Directives such as `.open`, `.create`, `.close`, `.include`, `.headersize`, `.nds`, and `.gba` are rejected. The patched target must remain exactly the same serialized size in this slice.

If `symbols` is requested, the `.sym` output is copied to the project only **after** the rebuilt ROM passes structural and touched-target verification. Failed assembler jobs do not produce the configured ROM output.

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

A build performs this sequence:

1. Parse the project manifest.
2. Resolve the source ROM and verify its SHA-256.
3. Load and structurally validate the NDS image.
4. Clean the temporary build workspace.
5. Apply changes in manifest order.
6. Run armips jobs only against copied targets under `build/work/armips/` when requested.
7. Snapshot every touched target for post-rebuild verification.
8. Serialize the ROM through the NDS backend.
9. Validate the serialized image.
10. Reload it through a fresh NDS parser.
11. Confirm every touched target survived rebuild exactly.
12. Materialize validated symbol outputs when requested.
13. Atomically write the output ROM.
14. Record hashes, mutations, validation state, and tool versions in `reports/build.json`.

A failed mutation, assembler, or validation stage does not write a partial configured output.

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

Coverage includes project initialization, source mismatch rejection, load/save/reload, metadata normalization, NitroFS extraction/replacement, overlay access, address mapping, guarded patch failures, deterministic builds, structural corruption detection, complete CLI workflow, safe armips-fragment validation, tool discovery, and real ARM9/ARM7/overlay armips patching when armips is available.

## Deferred NDS work

Current NDS work still does **not** include:

- automatic ARM/Thumb hooks and trampolines;
- code-cave discovery;
- symbol-aware hook/injection planning;
- compiled C/C++ injection;
- Keystone or Unicorn integration;
- BPS/IPS/xdelta patch-file generation;
- NitroFS create/delete operations;
- emulator-driven behavioral validation.

The immediate next NDS layer is symbol-aware hook and code-injection support on top of the proven armips pipeline.

## PSP status

PSP source references are intentionally parked. PSP support will begin only after the NDS modification path is mature enough to establish the shared interfaces without forcing PSP-specific design into the NDS foundation.
