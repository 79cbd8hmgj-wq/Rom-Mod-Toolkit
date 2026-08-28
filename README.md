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
- Build guarded symbol-aware ARM hooks plus short and long Thumb hooks into verified code caves.
- Require an explicit low scratch register for long-range Thumb veneers so register clobbering is never implicit.
- Compile freestanding ARM C payloads with Clang/LLD and inject them through the same guarded hook/cave pipeline.
- Link C `extern` references to validated ARM/data symbols and Thumb functions from the component-aware NDS analysis JSON.
- Generate ARM-to-Thumb call veneers automatically for C calls into analyzed Thumb functions, using `r12/ip` as ABI call-scratch and garbage-collecting unused veneers at link time.

## Requirements

- Python 3.10+
- `ndspy==4.2.0`
- `PyYAML>=6.0`
- `armips` 0.11-compatible executable when a project contains assembly or injection changes
- Clang with `arm-none-eabi` support, LLD, and `llvm-objcopy` when a project contains `type: c_inject` changes

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

### Automatic ARM/Thumb hook injection

`type: inject` builds a guarded hook from a named imported symbol, places the payload in reserved free space, and automatically returns to the first instruction after the overwritten hook. Imported symbol metadata selects ARM versus Thumb behavior.

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

The payload is a positionless fragment assembled in the hook symbol's instruction set. The toolkit owns `.org`, architecture/mode selection, the generated hook/veneer, the cave label, and the return path. File-owning/import directives remain forbidden.

For Thumb symbols, a cave inside the Thumb-1 unconditional branch range uses a 2-byte short hook. A farther cave uses an 8-byte literal-load veneer. Long Thumb hooks require `scratch_register: r0` through `r7`; that register is explicitly documented as clobbered by the veneer. The long return path uses the same scratch register and a fixed 8-byte return stub at the end of the reserved cave.

```yaml
changes:
  - type: inject
    target: arm9
    symbol_file: analysis/symbols.json
    hook: ThumbBattleDamage
    expected: "05 06 07 08 09 0A 0B 0C"
    script: asm/thumb_payload.asm
    cave: auto
    reserve: 24
    scratch_register: r3
```

`cave: auto` searches only the **trailing** run of the requested fill byte in the selected target, aligned to four bytes. It never treats an arbitrary internal zero run as executable free space. An explicit cave may instead be supplied as a CPU address. The reserved cave must already contain exactly the declared fill byte.

After armips runs, the toolkit diffs the complete target and rejects any changed byte outside the selected hook width or declared cave reserve. ARM hooks use 4 bytes, short Thumb hooks use 2 bytes, and long Thumb veneers use 8 bytes. The hook and cave cannot overlap, target size cannot change, and the configured ROM output is not written when any guard fails. Resolved hook/cave addresses, hook mode, hook size, and any scratch register are recorded in `reports/build.json`.

### Freestanding ARM C payload injection

`type: c_inject` turns a small C function into ARM machine code and installs it behind the same guarded 4-byte ARM hook used by the assembly injector. The required entry point is `rommod_payload`.

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
    reserve: 32
    fill: "00"
```

Example payload:

```c
extern int GameHelper(int value);

int rommod_payload(int value) {
    return GameHelper(value + 7);
}
```

The compiler runs freestanding for ARM946E-S in ARM mode with no standard library, no PIC/PIE, and function/data sections enabled. LLD places `rommod_payload` at the toolkit-selected cave address, and `llvm-objcopy` extracts only the executable image. Read-only constants may travel with the code; writable `.data`, `.bss`, COMMON storage, and a missing `rommod_payload` entry fail the build. The compiled payload must fit inside the declared cave after the toolkit's 8-byte call/return wrapper.

The same component-aware analysis JSON used for the hook is also validated before linking C externs. ARM function labels and neutral/data labels in the selected component are exposed to LLD as absolute addresses. Thumb function labels receive generated ARM veneers instead of unsafe direct ARM branches. Each veneer loads `thumb_address | 1` into `r12/ip` and branches through it, explicitly switching the CPU into Thumb state. Veneers live in separate link sections and LLD `--gc-sections` removes any that the C payload does not reference.

The wrapper branches from the hook to the cave, calls `rommod_payload` with `BL`, then branches back to `hook + 4`. It does **not** replay the overwritten instruction. Normal ARM procedure-call rules apply: C may modify caller-saved registers (`r0`-`r3`, `r12`, `lr`) and condition flags, so hook selection/payload design must account for the state expected by the original game code.

Compiler paths resolve from `tools.*`, then their `ROMMOD_*` environment overrides, then `PATH`. The build report records the resolved Clang, LLD, and llvm-objcopy versions plus C payload size, load address, and whether Thumb interworking was linked. Any compiler, linker, assembler, expected-byte, cave, size, or bounded-write failure prevents the configured ROM output from being written.

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

Coverage includes project initialization, source mismatch rejection, load/save/reload, metadata normalization, NitroFS extraction/replacement, overlay access, address mapping, guarded patch failures, deterministic builds, structural corruption detection, the complete CLI workflow, armips manifest/tool resolution, fragment safety, component-aware symbol import, address/offset validation, real ARM9/ARM7/overlay assembly builds, guarded ARM hook injection, short Thumb branches, explicit-scratch long Thumb veneers, freestanding ARM C compilation, writable-data rejection, bounded C injection, validated C calls into imported ARM game symbols, and generated ARM-to-Thumb interworking veneers.

## Deferred NDS work

The current NDS path does **not** yet include:

- broader code-cave/free-space discovery beyond guarded trailing fill runs;
- direct `c_inject` entry from Thumb hook sites;
- user-authored multi-object C/C++ builds and richer runtime support;
- Keystone or Unicorn integration;
- BPS/IPS/xdelta patch-file generation;
- NitroFS create/delete operations;
- emulator-driven behavioral validation.

The next coding-focused NDS work can extend `c_inject` to Thumb hook sites and then add user-authored multi-source linking, while patch distribution and broader free-space management remain separate follow-up layers.

## PSP status

PSP source references are intentionally parked. PSP support will begin only after the NDS modification path is mature enough to establish the shared interfaces without forcing PSP-specific design into the NDS foundation.
