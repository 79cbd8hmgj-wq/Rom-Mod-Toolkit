# Rom Mod Toolkit

`Rom-Mod-Toolkit` is an NDS-first toolkit for reproducible ROM inspection, extraction, modification, rebuild, verification, code injection, and distributable patch generation.

The NDS path always works from a SHA-256-locked source ROM plus declared mutations. The source ROM is never modified in place, and failed mutation, tool, rebuild, or verification stages do not leave a partially accepted configured output.

## Current NDS capabilities

- Initialize a Nintendo DS mod project and lock the source ROM by SHA-256.
- Inspect normalized NDS header, ARM9, ARM7, filesystem, and overlay metadata.
- Extract ARM9, ARM7, NitroFS files, and ARM9/ARM7 overlays for inspection.
- Replace existing NitroFS files.
- Apply exact guarded byte patches to ARM9, ARM7, overlays, or NitroFS files.
- Rebuild through `ndspy` and reparse the output before it is accepted.
- Verify key header ranges, FAT entries, overlay-table references, and fresh parsing.
- Produce deterministic build output for the same source, manifest, and dependency versions.
- Write a machine-readable `reports/build.json` with source/output hashes and applied mutations.
- Keep CPU addresses and target-relative file offsets as separate typed concepts.
- Run real `armips` fragments against isolated ARM9, ARM7, ARM9-overlay, or ARM7-overlay working copies.
- Import component-aware analysis symbols into armips while preserving ARM/Thumb identity.
- Build guarded symbol-aware ARM hooks plus short and long Thumb hooks into verified code caves.
- Compile freestanding C payloads with Clang/LLD and inject them from ARM or Thumb hook sites.
- Build one C payload from either one source file or multiple translation units.
- Apply shared project-relative include directories and validated preprocessor definitions to every C translation unit.
- Link C `extern` references to validated ARM/data symbols and Thumb functions from analysis JSON.
- Generate ARM-to-Thumb call veneers automatically for referenced Thumb functions.
- Discover aligned fill-run free-space candidates in ARM9, ARM7, and overlays without mutating the ROM.
- Create and round-trip verify BPS and IPS patches with Flips.
- Create and round-trip verify xdelta/VCDIFF patches with xdelta3.

## Requirements

- Python 3.10+
- `ndspy==4.2.0`
- `PyYAML>=6.0`
- `armips` when a project contains assembly or injection changes
- Clang with `arm-none-eabi` support, LLD, and `llvm-objcopy` when a project contains `type: c_inject` changes
- Flips for BPS/IPS patch generation
- xdelta3 for xdelta patch generation

For development/testing:

```bash
python -m pip install -e ".[test]"
pytest -q
```

The repository CI builds/resolves the real external tools used by the NDS path before running the full test suite.

## Command workflow

```bash
rommod init game.nds my-mod
rommod inspect my-mod
rommod extract my-mod
rommod caves my-mod --target arm9 --min-size 32 --fill 00 --alignment 4
rommod build my-mod
rommod verify my-mod
rommod patch my-mod --format bps
```

Patch formats are `bps`, `ips`, and `xdelta`.

You can also inspect or verify a standalone ROM:

```bash
rommod inspect game.nds
rommod verify game.nds
```

Toolkit validation errors are printed as concise `error: ...` diagnostics and return exit code `2`.

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

The configured source may live outside the project. Its SHA-256 is recorded in `rommod.yaml`; build, project verification, cave discovery, and patch distribution all enforce the locked source.

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

Creating or deleting NitroFS entries is intentionally not part of the current slice.

### Guarded byte patch

Every byte patch includes the bytes expected at the target location. A mismatch aborts the build.

```yaml
changes:
  - type: byte_patch
    target: arm9
    offset: 0x1234
    expected: "01 02 03 04"
    replacement: "AA BB CC DD"
```

Supported byte-patch targets are:

```text
arm9
arm7
overlay9:<overlay-id>
overlay7:<overlay-id>
file:<nitrofs/path>
```

`offset` is always a target-relative serialized-file offset, not a CPU address.

## ARM/Thumb assembly patching

Assembly fragments run against isolated target copies under `build/work/`; armips never receives the source ROM directly.

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

Supported code targets are `arm9`, `arm7`, `overlay9:<id>`, and `overlay7:<id>`. The toolkit wrapper selects the architecture and maps `.org` CPU addresses to the target RAM base. A fragment may switch between ARM and Thumb.

For safety, user fragments cannot take ownership of files or architecture selection with directives such as `.open`, `.create`, `.close`, `.include`, `.headersize`, `.nds`, or `.gba`. Patched targets must remain exactly the same serialized size.

### Import analysis symbols into armips

An armips change can import the component-aware JSON emitted by an NDS analysis/disassembly workflow:

```yaml
changes:
  - type: armips
    target: overlay9:0
    script: asm/battle_patch.asm
    symbol_file: analysis/symbols.json
    symbol_component: battle_overlay
```

Accepted symbol files are a JSON array or an object with a `symbols` array. Records carry component identity, runtime address, component-relative offset, name, and optional `instruction_set` (`arm`, `thumb`, or null). Runtime address alone is not treated as globally unique because overlays may overlap in RAM.

Imported symbols are validated against the selected target mapping. Address/offset disagreement, out-of-range symbols, unsafe identifiers, duplicate names, or a missing requested component fail closed.

## Guarded hook injection

`type: inject` builds a guarded hook from a named imported symbol, installs an assembly payload in a declared cave, and returns to the first instruction after the overwritten hook.

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

For Thumb hooks, a reachable cave uses a 2-byte Thumb-1 branch. A farther cave uses an 8-byte literal-load veneer and requires an explicit `scratch_register: r0` through `r7`, making clobbering explicit.

`cave: auto` remains deliberately conservative: it searches only the **trailing** run of the declared fill byte in the selected target, aligned to four bytes. An explicit cave may instead be supplied as a CPU address. The entire reserved cave must already contain the declared fill byte.

After armips runs, the toolkit diffs the target and rejects any write outside the selected hook width or declared cave reserve. Hook/cave overlap, target resizing, expected-byte mismatch, and bounded-write violations fail the build.

## Free-space discovery

Use `rommod caves` to inspect broader candidate fill runs without weakening `cave: auto`:

```bash
rommod caves my-mod --target overlay9:3 --min-size 48 --fill FF --alignment 8
```

The scanner verifies the source lock, reads the selected code target, identifies maximal fill-byte runs, aligns each candidate in CPU-address space, and reports:

- target-relative offset;
- runtime CPU address;
- usable aligned size;
- fill byte;
- whether the run is trailing.

A discovered run is only a **candidate**. It is not proof that the region is unused or executable-safe. Discovery is read-only and never feeds internal runs into injection automatically. If analysis establishes that an internal candidate is safe, use its reported CPU address explicitly as the manifest `cave`; the normal injection fill and bounded-write guards still apply.

## Freestanding C payload injection

`type: c_inject` compiles freestanding C into ARM machine code and installs it behind the guarded ARM/Thumb hook pipeline. The required entry point is `rommod_payload`.

Single source example:

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
    fill: "00"
```

Multiple translation units can be linked as one payload:

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
      ROMMOD_FEATURE: "1"
      DAMAGE_SCALE: "3"
    cave: auto
    reserve: 96
    fill: "00"
```

A C injection provides exactly one of `source` or `sources`. Shared `include_dirs` are resolved inside the project and passed to every translation unit. `defines` are validated and supplied consistently to every translation unit as preprocessor definitions.

The compiler runs freestanding for ARM946E-S in ARM mode with no standard library, PIC/PIE, writable static data, or COMMON storage. LLD places `rommod_payload` at the toolkit-selected code address and `llvm-objcopy` extracts the executable image. The compiled image must fit inside the declared reserve after the toolkit bridge/wrapper.

C can call validated ARM/data symbols directly. Thumb function symbols receive generated ARM-to-Thumb veneers that load `thumb_address | 1` into `r12/ip` and branch through it; unused veneer sections are garbage-collected by LLD.

C injection also supports Thumb hook sites. The toolkit selects the appropriate short/long Thumb entry bridge, switches into ARM state for the compiled payload, and returns to the correct Thumb continuation address. Long Thumb entry still requires an explicit low scratch register.

Build reports record C source configuration, include directories/defines where configured, payload size/address, hook mode/size, Thumb interworking state, and resolved Clang/LLD/objcopy versions.

## Patch distribution

`rommod patch` always builds the source-locked project first, creates a patch from the verified source to that exact rebuilt target, applies the new patch into a temporary verification file, and accepts the patch only if the reconstructed bytes hash exactly to the built target.

```bash
rommod patch my-mod --format bps
rommod patch my-mod --format ips --output patches/release.ips
rommod patch my-mod --format xdelta --output patches/release.xdelta
```

BPS/IPS use Flips. xdelta uses xdelta3. Tool paths may be configured through the toolkit tool configuration/environment resolution path. Patch reports record source, target, and patch hashes plus the resolved patch tool/version and round-trip verification state.

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

Extraction is for inspection and authoring. Builds do not blindly rebuild from this directory; they start from the verified source ROM and apply only manifest-declared changes.

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
12. Record hashes, mutations, validation state, and tool versions in `reports/build.json`.

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

`ndspy` may repack regions, align sections, update FAT offsets, and recalculate header values when saving. An untouched rebuild is expected to be deterministic and structurally equivalent, but it is not universally required to be byte-for-byte identical to the source ROM.

## Tests

The test suite uses a programmatically generated synthetic Nintendo DS fixture; no proprietary commercial ROM is required.

Coverage includes project/source locking, load/save/reload, extraction and NitroFS replacement, overlay access, address mapping, guarded byte patches, deterministic builds, structural validation, CLI workflows, real armips patching, component-aware symbol imports, ARM/Thumb hook injection, freestanding C compilation, multi-source/include/define handling, C-to-Thumb interworking, read-only free-space discovery, and verified BPS/IPS/xdelta distribution.

## Deferred NDS work

The current NDS path intentionally does **not** yet include:

- automatic proof that an internal fill-run candidate is unused/executable-safe;
- C++ runtime support, constructors, exceptions, or a richer freestanding runtime;
- Keystone or Unicorn integration;
- NitroFS create/delete operations;
- emulator-driven behavioral validation.

These are follow-up layers rather than blockers for the completed NDS modification pipeline.

## PSP status

PSP source references remain intentionally parked while the NDS-first architecture is established. PSP work can build on the shared project/build/verification/tool-resolution interfaces without forcing PSP-specific behavior into the NDS implementation.
