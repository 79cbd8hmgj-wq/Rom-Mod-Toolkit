# Rom Mod Toolkit

`Rom-Mod-Toolkit` is an NDS-first toolkit for reproducible ROM inspection, extraction, modification, rebuild, code injection, verification, and patch distribution.

The NDS implementation always starts from a SHA-256-locked source ROM and applies declared project changes. The source ROM is never modified in place. PSP remains intentionally parked until the NDS path establishes the shared architecture.

## Current NDS capabilities

- Initialize a mod project and lock the source ROM by SHA-256.
- Inspect normalized NDS header, ARM9, ARM7, NitroFS, and overlay metadata.
- Extract ARM9, ARM7, NitroFS files, and ARM9/ARM7 overlays.
- Replace existing NitroFS files.
- Apply guarded exact byte patches to ARM9, ARM7, overlays, and NitroFS files.
- Run sandboxed armips fragments against isolated ARM9/ARM7/overlay working copies.
- Import component-aware analysis symbols into armips.
- Build guarded symbol-aware ARM hooks and short/long Thumb hooks.
- Select guarded trailing-fill code caves automatically or use explicit CPU addresses.
- Compile and inject freestanding ARM C payloads through ARM or Thumb hook sites.
- Link C calls/references against validated analyzed ARM/data symbols.
- Generate ARM-to-Thumb interworking veneers automatically for analyzed Thumb functions.
- Compile multi-source C payloads.
- Share project-contained C include directories across translation units.
- Pass validated per-change C preprocessor definitions (`-D`).
- Rebuild through `ndspy`, reparse the result, and verify every declared touched target survived rebuild exactly.
- Produce machine-readable build reports with hashes, mutation metadata, tool paths, and versions.
- Generate and re-apply verified BPS, IPS, and xdelta patches before atomically publishing them.

## Requirements

Core:

- Python 3.10+
- `ndspy==4.2.0`
- `PyYAML>=6.0`

Feature-specific external tools:

- `armips` for assembly patches and hook/injection changes.
- Clang with `arm-none-eabi` support, LLD, and `llvm-objcopy` for `type: c_inject`.
- Floating IPS (`flips`) for BPS/IPS patch distribution.
- `xdelta3` for xdelta patch distribution.

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
rommod patch my-mod --format bps
```

Other patch formats:

```bash
rommod patch my-mod --format ips
rommod patch my-mod --format xdelta
```

A custom project-relative patch path may be supplied with `--output`.

Standalone ROMs may also be inspected or structurally verified:

```bash
rommod inspect game.nds
rommod verify game.nds
```

Toolkit validation errors are emitted as concise `error: ...` diagnostics and return exit code `2`.

## Project layout

`rommod init` creates a project similar to:

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

The configured source ROM may live outside the project. Its SHA-256 is recorded in `rommod.yaml`; builds, verification, and patch distribution fail if that source changes.

## Manifest basics

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

### NitroFS replacement

```yaml
changes:
  - type: file_replace
    target: data/example.bin
    source: files/example.bin
```

The current NDS path replaces existing NitroFS entries only. Creating/deleting entries is deferred.

### Guarded byte patch

```yaml
changes:
  - type: byte_patch
    target: arm9
    offset: 0x1234
    expected: "01 02 03 04"
    replacement: "AA BB CC DD"
```

Supported targets are:

```text
arm9
arm7
overlay9:<overlay-id>
overlay7:<overlay-id>
file:<nitrofs/path>
```

For `byte_patch`, `offset` is a target-relative serialized-file offset, not a CPU address.

## armips patches

Assembly runs only against an isolated target copy under `build/work/`; armips never receives the source ROM.

```yaml
tools:
  armips: /path/to/armips

changes:
  - type: armips
    target: arm9
    script: asm/battle_patch.asm
    symbol_file: analysis/symbols.json
    symbols: reports/battle_patch.sym
```

Fragments may use ARM/Thumb mode and CPU-address `.org` directives, while file-owning/import directives that would escape toolkit control are rejected. Patched target size must remain unchanged.

Tool resolution order is manifest configuration, the matching `ROMMOD_*` environment variable, then `PATH`.

## Symbol-aware hook injection

`type: inject` resolves a named analyzed symbol, verifies expected bytes, chooses ARM/Thumb hook behavior, installs a branch/veneer, and bounds every modified byte to the hook or reserved cave.

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
```

For Thumb symbols, nearby caves use a 2-byte short branch. Distant caves use an 8-byte literal-load veneer and require an explicit low scratch register (`r0`-`r7`) so clobbering is never implicit.

`cave: auto` deliberately searches only the trailing run of the requested fill byte, aligned to four bytes. It does not assume arbitrary internal zero runs are safe executable space. An explicit cave may be supplied as a CPU address.

## Freestanding C injection

`type: c_inject` compiles C for ARM946E-S and installs the payload through the same guarded hook/cave system. The required entry function is `rommod_payload`.

Single-source example:

```yaml
tools:
  armips: /path/to/armips
  clang: /path/to/clang
  ld_lld: /path/to/ld.lld
  llvm_objcopy: /path/to/llvm-objcopy

changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleDamage
    expected: "05 06 07 08"
    source: src/battle_damage.c
    cave: auto
    reserve: 64
```

Multi-source projects may instead use `sources`, shared include directories, and definitions:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleDamage
    expected: "05 06 07 08"
    sources:
      - src/payload.c
      - src/helper.c
      - src/battle_math.c
    include_dirs:
      - include
      - src/common
    defines:
      - GAME_REGION_US
      - DAMAGE_MULTIPLIER=3
    cave: auto
    reserve: 96
```

Include directories are project-contained, must exist, and are passed identically to every translation unit. Definitions must begin with valid C macro identifiers and are passed directly to Clang as separate `-D` argv values.

The linker exposes validated component symbols to C. Analyzed Thumb functions receive generated ARM-to-Thumb veneers that branch through `r12/ip` with bit 0 set; unused veneers are garbage-collected by LLD.

C payloads may enter through ARM hooks or supported short/long Thumb hooks. Writable `.data`, `.bss`, COMMON storage, missing `rommod_payload`, oversized payloads, invalid symbols, unsafe cave writes, or external-tool failures abort the build.

## Verified patch distribution

Patch generation is platform-neutral under `src/rommod/patching/` so it can be reused by later platform adapters.

Examples:

```bash
rommod patch my-mod --format bps
rommod patch my-mod --format ips
rommod patch my-mod --format xdelta
```

Configuration is optional when the tools are available through environment variables or `PATH`:

```yaml
tools:
  flips: /path/to/flips
  xdelta3: /path/to/xdelta3
```

A patch command:

1. verifies the locked source ROM;
2. performs a fresh normal project build;
3. creates the patch in temporary build space;
4. applies that patch back to the locked source;
5. verifies decoded target size and SHA-256 against the fresh build;
6. atomically publishes the patch only after the round trip succeeds;
7. writes `reports/patch-bps.json`, `reports/patch-ips.json`, or `reports/patch-xdelta.json`.

BPS/IPS use Floating IPS. xdelta uses `xdelta3`.

## Build safety

An NDS build performs this sequence:

1. Parse the manifest.
2. Resolve and SHA-256-verify the source ROM.
3. Load and structurally validate the NDS image.
4. Clean temporary build workspace.
5. Apply changes in manifest order.
6. Snapshot every touched target.
7. Serialize through the NDS backend.
8. Validate the serialized image.
9. Reload it through a fresh parser.
10. Confirm every touched target survived rebuild exactly.
11. Atomically write the configured ROM.
12. Record hashes, mutations, validation state, and external-tool metadata in `reports/build.json`.

A failed mutation or validation stage does not publish a partial configured output.

## Verification scope

`rommod verify` currently checks structural properties including:

- minimum NDS header size;
- ARM9/ARM7 ranges;
- FNT/FAT and overlay-table ranges;
- FAT alignment and entry bounds;
- overlay-table record alignment;
- overlay file IDs against FAT;
- fresh parser acceptance.

This is structural validation, not proof of correct gameplay behavior in an emulator.

## Rebuild equivalence

`ndspy` may repack regions, align sections, update FAT offsets/header values, and recalculate header values while saving. An untouched rebuild is therefore required to be deterministic and structurally equivalent, but is not universally required to be byte-for-byte identical to the source ROM.

## Testing

The suite uses a programmatically generated synthetic NDS fixture; no proprietary commercial ROM is required.

GitHub Actions builds real copies of armips, Floating IPS, and xdelta3 and uses real Clang/LLD/llvm-objcopy. The latest completed distribution milestone verified the complete suite with:

```text
124 passed
```

Coverage spans source locking, ROM loading/rebuilding, extraction, NitroFS replacement, overlays, address mapping, guarded byte patches, structural corruption handling, armips sandboxing, component-aware symbols, ARM/Thumb hooks, C injection through ARM/Thumb entry sites, ARM-to-Thumb interworking, multi-source C, include directories, preprocessor definitions, and real BPS/IPS/xdelta round trips.

## Intentionally deferred NDS work

The completed NDS-first milestone does not attempt to make unsafe assumptions about arbitrary ROM space. The following remain separate future enhancements:

- broader code-cave/free-space discovery beyond guarded trailing fill runs;
- richer C/C++ runtime support beyond the current freestanding payload model;
- Keystone integration for additional programmatic assembly workflows;
- Unicorn integration for isolated ARM execution/emulation tests;
- NitroFS create/delete operations;
- emulator-driven behavioral validation.

These are extensions rather than missing requirements for the current extraction → modification → rebuild → verification → patch-distribution path.

## PSP status

PSP source references are intentionally parked. PSP implementation should begin after the completed NDS path is used as the shared architectural baseline, without forcing PSP-specific ELF/PRX assumptions into NDS code.

Detailed implementation records are under `docs/superpowers/plans/`.
