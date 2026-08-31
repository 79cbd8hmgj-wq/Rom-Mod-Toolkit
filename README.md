# Rom Mod Toolkit

`Rom-Mod-Toolkit` is an NDS-first toolkit for reproducible ROM inspection, extraction, modification, rebuild, verification, code injection, and distributable patch generation.

The NDS path always works from a SHA-256-locked source ROM plus declared mutations. The source ROM is never modified in place, and failed mutation, tool, rebuild, or verification stages do not leave a partially accepted configured output.

## Current NDS capabilities

- Initialize a Nintendo DS mod project and lock the source ROM by SHA-256.
- Inspect normalized NDS header, ARM9, ARM7, filesystem, and overlay metadata.
- Extract ARM9, ARM7, NitroFS files, and ARM9/ARM7 overlays.
- Replace existing NitroFS files.
- Apply exact guarded byte patches to ARM9, ARM7, overlays, or NitroFS files.
- Rebuild through `ndspy`, structurally validate, and freshly reparse the output.
- Verify touched targets survive serialization exactly.
- Record source/output hashes, mutations, validation state, and external tool versions.
- Keep CPU addresses and target-relative file offsets as separate typed concepts.
- Run real `armips` fragments against isolated ARM9, ARM7, and overlay working copies.
- Import component-aware analysis symbols while preserving ARM/Thumb identity.
- Build guarded ARM hooks plus short and long Thumb hooks into verified code caves.
- Compile freestanding C payloads with Clang/LLD and inject them from ARM or Thumb hook sites.
- Link either one C source or multiple translation units with shared include directories and preprocessor definitions.
- Link C `extern` references to validated ARM/data symbols and generated ARM-to-Thumb veneers.
- Discover aligned fill-run free-space candidates in ARM9, ARM7, and overlays without mutating the ROM.
- Create and round-trip verify BPS/IPS patches with Flips and xdelta/VCDIFF patches with xdelta3.

## Requirements

- Python 3.10+
- `ndspy==4.2.0`
- `PyYAML>=6.0`
- `armips` for assembly/injection changes
- Clang with `arm-none-eabi` support, LLD, and `llvm-objcopy` for `type: c_inject`
- Flips for BPS/IPS patch generation
- xdelta3 for xdelta patch generation

For development/testing:

```bash
python -m pip install -e ".[test]"
pytest -q
```

Repository CI builds/resolves the real external tools used by the NDS path before running the full suite.

## Main workflow

```bash
rommod init game.nds my-mod
rommod inspect my-mod
rommod extract my-mod
rommod caves my-mod --target arm9 --min-size 32 --fill 00 --alignment 4
rommod build my-mod
rommod verify my-mod
rommod patch my-mod --format bps
```

Patch formats are `bps`, `ips`, and `xdelta`. A standalone ROM can also be inspected or verified directly.

Toolkit validation errors are printed as `error: ...` diagnostics and return exit code `2`.

## Project layout

`rommod init` creates a project shell like:

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

The configured source may live outside the project. Its SHA-256 is recorded in `rommod.yaml`; build, verification, cave discovery, and patch distribution enforce that lock.

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

### NitroFS replacement

```yaml
changes:
  - type: file_replace
    target: data/example.bin
    source: files/example.bin
```

Creating or deleting NitroFS entries is intentionally not part of the current slice.

### Guarded byte patch

```yaml
changes:
  - type: byte_patch
    target: arm9
    offset: 0x1234
    expected: "01 02 03 04"
    replacement: "AA BB CC DD"
```

Supported targets are `arm9`, `arm7`, `overlay9:<id>`, `overlay7:<id>`, and NitroFS files. Byte-patch `offset` is target-relative, not a CPU address. Expected-byte mismatch aborts the build.

## ARM/Thumb assembly patching

Assembly fragments run against isolated target copies; armips never receives the source ROM directly.

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

The wrapper selects the target architecture and maps CPU-address `.org` values to the target RAM base. User fragments cannot take ownership of files/architecture selection through directives such as `.open`, `.create`, `.close`, `.include`, `.headersize`, `.nds`, or `.gba`. Patched targets must retain their serialized size.

### Component-aware analysis symbols

Assembly and injection changes can import the NDS analysis/disassembly JSON:

```yaml
changes:
  - type: armips
    target: overlay9:0
    script: asm/battle_patch.asm
    symbol_file: analysis/symbols.json
    symbol_component: battle_overlay
```

Symbols carry component identity, runtime address, component-relative offset, name, and optional `instruction_set`. Runtime address alone is not globally unique because overlays can overlap in RAM. Address/offset disagreement, out-of-range symbols, unsafe identifiers, duplicate names, and missing components fail closed.

## Guarded hook injection

`type: inject` builds a hook from an imported symbol, installs an assembly payload into a declared cave, and returns after the overwritten hook.

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

ARM hooks use a guarded branch. A reachable Thumb cave uses a 2-byte Thumb-1 branch; a farther Thumb cave uses an 8-byte literal-load veneer and requires an explicit `scratch_register: r0` through `r7`.

`cave: auto` remains deliberately conservative: it searches only the **trailing** run of the declared fill byte in the selected target, aligned to four bytes. An explicit cave may instead be a CPU address. The entire reserve must match the declared fill byte. After armips runs, writes outside the hook/cave ranges, hook/cave overlap, resizing, or expected-byte mismatch are rejected.

## Free-space discovery

Use `rommod caves` to inspect broader fill-run candidates without weakening `cave: auto`:

```bash
rommod caves my-mod --target overlay9:3 --min-size 48 --fill FF --alignment 8
```

The scanner verifies the source lock, scans only the selected ARM9/ARM7/overlay target, aligns candidate starts in CPU-address space, and reports target-relative offset, runtime address, usable aligned size, fill byte, and whether the run is trailing.

A reported run is a **candidate**, not proof that it is unused or executable-safe. Discovery is read-only and internal candidates are never fed automatically into injection. If analysis establishes that one is safe, its reported CPU address can be selected explicitly as the manifest `cave`; normal fill and bounded-write guards still apply.

## Freestanding C injection

`type: c_inject` compiles freestanding C for ARM946E-S and installs it behind the guarded ARM/Thumb hook pipeline. The required entry point is `rommod_payload`.

Single source:

```yaml
changes:
  - type: c_inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: BattleDamage
    expected: "05 06 07 08"
    source: src/battle_damage.c
    cave: auto
    reserve: 48
```

Multiple translation units, includes, and defines:

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
    include_dirs:
      - include
      - src/common
    defines:
      - ROMMOD_FEATURE=1
      - DAMAGE_SCALE=3
    cave: auto
    reserve: 96
```

A C injection provides exactly one of `source` or `sources`. `include_dirs` are project-contained directories applied to every translation unit. `defines` is a list of validated `NAME` or `NAME=value` strings applied to every translation unit.

Writable `.data`, `.bss`, COMMON storage, PIC/PIE, and missing `rommod_payload` are rejected. The linked image must fit inside the reserved cave after the toolkit bridge. C can link validated ARM/data symbols directly; Thumb functions receive generated interworking veneers and unused veneers are garbage-collected.

C injection supports ARM and Thumb hook sites. The toolkit selects the short/long Thumb entry bridge, switches into ARM state for the compiled payload, and returns to the correct Thumb continuation address. Long Thumb entry requires an explicit low scratch register.

## Patch distribution

`rommod patch` builds the source-locked project first, creates a patch from the verified source to that exact rebuilt target, reapplies the patch into a temporary verification file, and accepts it only if the reconstructed bytes hash exactly to the target.

```bash
rommod patch my-mod --format bps
rommod patch my-mod --format ips --output patches/release.ips
rommod patch my-mod --format xdelta --output patches/release.xdelta
```

BPS/IPS use Flips. xdelta uses xdelta3. Patch reports record source, target, and patch hashes plus the resolved patch tool/version and round-trip verification state.

## Extraction and build safety

`rommod extract` refreshes `build/extracted/` with metadata, ARM9/ARM7 binaries, NitroFS files, and overlay data for inspection/authoring. Builds do **not** blindly rebuild from that directory; they always start from the verified source ROM and declared manifest changes.

An NDS build:

1. parses the manifest and verifies source SHA-256;
2. loads and structurally validates the source image;
3. applies declared changes in order in an isolated workspace;
4. snapshots touched targets;
5. serializes through the NDS backend;
6. validates and freshly reparses the rebuilt image;
7. confirms every touched target survived exactly;
8. atomically writes the configured output;
9. records hashes, mutations, validation state, and tool versions.

`rommod verify` checks core header ranges, ARM9/ARM7 ranges, FNT/FAT and overlay-table ranges, FAT alignment/bounds, overlay file references, and a fresh parse. This is structural verification, not emulator proof.

`ndspy` may repack/alignment-adjust regions and recalculate header/FAT values when saving, so an untouched rebuild is expected to be deterministic and structurally equivalent rather than universally byte-identical.

## Tests

The suite uses programmatically generated synthetic Nintendo DS fixtures; proprietary commercial ROM data is not required.

Coverage includes project/source locking, ROM round-trip, extraction/NitroFS replacement, overlays, address mapping, guarded byte patches, deterministic builds, structural validation, CLI workflows, real armips patching, component-aware symbols, ARM/Thumb hooks, freestanding C compilation, multi-source/include/define handling, C-to-Thumb interworking, read-only free-space discovery, and verified BPS/IPS/xdelta distribution.

## Deferred NDS work

The current NDS path intentionally does **not** yet include:

- automatic proof that an internal fill-run candidate is unused/executable-safe;
- C++ runtime support, constructors, exceptions, or a richer freestanding runtime;
- Keystone or Unicorn integration;
- NitroFS create/delete operations;
- emulator-driven behavioral validation.

These are follow-up layers rather than blockers for the NDS modification pipeline defined by the original implementation plan.

## PSP status

PSP source references remain intentionally parked while the NDS-first architecture is established. PSP work can build on the shared project/build/verification/tool-resolution interfaces without forcing PSP-specific behavior into the NDS implementation.
