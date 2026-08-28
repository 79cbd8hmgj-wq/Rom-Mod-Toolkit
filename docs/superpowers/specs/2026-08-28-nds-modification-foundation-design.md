# NDS Modification Foundation — Design

Date: 2026-08-28
Status: Approved design, awaiting implementation plan
Repository: `79cbd8hmgj-wq/Rom-Mod-Toolkit`

## 1. Purpose

Build the first production platform path for Rom Mod Toolkit around Nintendo DS ROM modification. The NDS implementation proves the shared toolkit architecture before PSP support is introduced.

The first milestone is deliberately narrower than a full ROM-hacking SDK: it must reliably load, inspect, extract, modify, rebuild, verify, and patch an NDS ROM. Advanced code injection, free-space discovery, C linking, and emulator-driven behavioral tests follow only after the rebuild path is trustworthy.

## 2. Design principles

1. **NDS first, shared core secondarily reusable.** Shared abstractions must be useful for NDS now and extensible to PSP later, but PSP-specific requirements must not distort Phase 1.
2. **Wrap proven source behavior before reimplementing formats.** Use `ndspy` as the primary reference/backend for NDS container, code, overlay, FNT/FAT, and NitroFS operations where its behavior is sufficient.
3. **Keep external tools behind adapters.** `armips`, Flips, and xdelta are invoked through stable toolkit interfaces so they can be replaced or supplemented later.
4. **Never modify the user's source ROM in place.** All modifications operate on a project working copy and write a new output ROM.
5. **Reproducibility before injection.** Untouched extract/build projects must rebuild deterministically before advanced binary rewriting is enabled by default.
6. **Manifest every mutation.** File replacements, byte patches, assembly patches, and build outputs must be traceable from project configuration.
7. **Fail closed on ambiguous addresses or incompatible inputs.** A patch must not silently land at a guessed offset.

## 3. Source responsibilities

### ndspy

Phase 1 relies on the following observed `ndspy` capabilities:

- `NintendoDSRom.fromFile(...)` for loading a ROM.
- `NintendoDSRom.save(...)` / `saveToFile(...)` for rebuilding.
- `loadArm9()` and `loadArm7()` for main code files.
- `loadArm9Overlays()` and `loadArm7Overlays()` for overlay access.
- `getFileByName(...)` and `setFileByName(...)` for NitroFS files.
- `MainCodeFile` and `Overlay` abstractions for code sections and serialization.
- Overlay table load/save support.

Rom Mod Toolkit will wrap these operations rather than exposing `ndspy` objects directly through its public API.

### armips

Phase 1 uses `armips` as the external assembler/patch engine for ARM7, ARM9, and Thumb modifications. Relevant observed features include:

- `.nds` architecture selection.
- `.arm` and `.thumb` instruction modes.
- `.open` / `.close` output handling.
- `.org` / `.orga` address positioning.
- symbol/label definitions and symbol-file generation.

The toolkit will generate or run explicit assembly jobs against extracted working binaries. It will not allow assembly scripts to write directly to the original ROM.

### Flips and xdelta

These remain external patch backends in the first milestone:

- Flips: BPS/IPS patch creation where supported.
- xdelta: VCDIFF/xdelta patch creation for larger or more general binary differences.

The core patch API will not encode backend-specific behavior into project manifests.

### Keystone and Unicorn

Both are intentionally deferred from the first rebuild milestone:

- Keystone is reserved for later programmatic ARM/Thumb assembly.
- Unicorn is reserved for later isolated execution/validation of injected ARM routines.

## 4. Repository architecture

```text
Rom-Mod-Toolkit/
├── pyproject.toml
├── README.md
├── src/
│   └── rommod/
│       ├── __init__.py
│       ├── cli.py
│       ├── errors.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── hashes.py
│       │   ├── paths.py
│       │   └── subprocesses.py
│       ├── projects/
│       │   ├── __init__.py
│       │   ├── manifest.py
│       │   ├── project.py
│       │   └── workspace.py
│       ├── patching/
│       │   ├── __init__.py
│       │   ├── bytepatch.py
│       │   ├── formats.py
│       │   └── external.py
│       └── platforms/
│           ├── __init__.py
│           └── nds/
│               ├── __init__.py
│               ├── rom.py
│               ├── metadata.py
│               ├── filesystem.py
│               ├── binaries.py
│               ├── overlays.py
│               ├── addresses.py
│               ├── assembler.py
│               ├── rebuild.py
│               └── validation.py
├── tests/
│   ├── unit/
│   └── integration/
├── examples/
└── docs/
```

Files may be split further if implementation pressure shows a unit has more than one responsibility; the public boundaries above should remain stable.

## 5. Project model

A mod project is a directory containing an immutable reference to the source-ROM identity, a working area, modifications, and generated output.

```text
my-mod/
├── rommod.yaml
├── patches/
├── asm/
├── files/
├── build/
│   ├── extracted/
│   ├── work/
│   └── output/
└── reports/
```

The source ROM itself does not need to be copied into the project if the manifest points to it, but every build records its cryptographic identity before doing work.

### Initial manifest

```yaml
schema_version: 1
platform: nds

source:
  rom: game.nds
  sha256: <known source hash>

output:
  rom: build/output/game-modded.nds

changes: []
```

`sha256` is required after project initialization. Subsequent builds reject a source file whose hash differs unless the user explicitly re-initializes or updates the project source identity through a dedicated command.

## 6. Core NDS model

The public NDS facade owns an `ndspy.rom.NintendoDSRom` internally but returns toolkit-owned models.

### `NdsRom`

Responsibilities:

- load and validate an NDS image;
- expose normalized ROM metadata;
- provide controlled access to ARM9, ARM7, overlays, and NitroFS;
- apply toolkit mutation objects;
- serialize a rebuilt image.

It must not contain CLI logic, patch-file generation, workspace path management, or subprocess execution.

### Metadata

Normalized metadata includes at minimum:

- title;
- game code;
- maker code;
- ROM version;
- ARM9 ROM offset, entry address, RAM address, and size;
- ARM7 ROM offset, entry address, RAM address, and size;
- FNT/FAT locations;
- overlay table locations;
- banner location;
- source size and SHA-256.

The raw header remains available internally for validation but is not the stable public interface.

### Filesystem

`NdsFilesystem` maps normalized NitroFS paths to file IDs and bytes. Initial mutation support is replacement-only. Creating or deleting filesystem entries is deferred until the rebuild invariants for changed FNT/FAT layouts are covered by integration tests.

### Main binaries

`NdsBinary` identifies:

- processor: ARM9 or ARM7;
- RAM base;
- entry address;
- current bytes;
- compression state where determinable;
- source/build identity.

The implementation may use `ndspy.code.MainCodeFile` internally, including section-aware parsing when available.

### Overlays

`NdsOverlay` identifies:

- processor;
- overlay ID;
- RAM address;
- RAM size;
- BSS size;
- static initializer range when available;
- file ID;
- compression flags/state;
- bytes.

Overlay serialization must preserve table metadata that the user did not change.

## 7. Mutation model

Phase 1 supports three mutation classes.

### File replacement

```yaml
- type: file_replace
  target: /data/example.bin
  source: files/example.bin
```

The target path must already exist during Phase 1.

### Exact byte patch

```yaml
- type: byte_patch
  target: arm9
  offset: 0x1234
  expected: "01 02 03 04"
  replacement: "AA BB CC DD"
```

Every byte patch requires expected original bytes. Build failure is mandatory if they do not match.

Targets initially include:

- `arm9`;
- `arm7`;
- `overlay9:<id>`;
- `overlay7:<id>`;
- a named NitroFS file.

Offsets in `byte_patch` are target-relative file offsets, not CPU addresses.

### Assembly patch

```yaml
- type: armips
  target: arm9
  script: asm/battle_patch.asm
  symbols: reports/battle_patch.sym
```

The toolkit extracts the selected target into the build workspace, invokes armips against the working copy, validates process success and output boundaries, then returns the modified target to the NDS rebuild pipeline.

Direct whole-ROM armips writes are not part of Phase 1 because they bypass mutation accounting and source protection.

## 8. Address handling

CPU addresses and file offsets are distinct types at the toolkit boundary. Integer values must not be freely interchanged between them.

Phase 1 address services support deterministic mapping inside known ARM9, ARM7, and overlay regions. A CPU-address request outside a known mapped region fails with an explicit error rather than falling back to a raw ROM offset.

Later phases may add symbol-backed and section-backed address resolution.

## 9. Build pipeline

`rommod build` performs these stages in order:

1. Parse and validate `rommod.yaml`.
2. Resolve the source ROM and verify SHA-256.
3. Load and structurally validate the source NDS.
4. Create a clean build workspace.
5. Materialize mutable targets from the source ROM.
6. Apply manifest changes in declared order.
7. Reinsert changed NitroFS files, binaries, and overlays.
8. Serialize the rebuilt ROM through the NDS backend.
9. Run structural validation on the rebuilt ROM.
10. Write output atomically.
11. Write a machine-readable build report containing source hash, output hash, applied changes, external tool versions, warnings, and validation results.

A failed stage must not leave a partially-written output at the configured output path.

## 10. Extract pipeline

`rommod extract` produces a human-inspectable project snapshot without making it the source of truth for rebuilds.

Initial extraction includes:

- ROM metadata JSON;
- ARM9 binary;
- ARM7 binary;
- ARM9 overlays;
- ARM7 overlays;
- NitroFS files preserving their paths;
- overlay metadata JSON;
- source hash report.

Extraction is primarily for inspection and authoring modifications. The build continues to start from the verified source ROM plus declared mutations, which prevents stale extracted files from silently changing outputs.

## 11. Validation

Validation is layered.

### Input validation

- file exists and is readable;
- ROM is large enough to contain the required NDS header fields;
- key declared offsets/ranges are in bounds;
- ARM9/ARM7 ranges do not exceed image bounds;
- FNT/FAT and overlay table ranges are internally plausible;
- source SHA-256 matches the project.

### Mutation validation

- referenced NitroFS targets exist;
- overlay IDs exist on the requested processor;
- byte-patch expected bytes match;
- replacement and patch paths stay inside the project root;
- external tool executable is resolved explicitly;
- armips exits successfully and produces the expected working target.

### Rebuild validation

- rebuilt image parses successfully;
- core identity fields remain consistent unless explicitly mutable later;
- ARM9/ARM7 and filesystem regions are readable;
- overlays referenced by tables resolve;
- manifest-requested changes are present;
- output SHA-256 and size are recorded.

Exact byte-for-byte equality is required for the untouched-rebuild fixture only when the backend can preserve layout identically. Otherwise the acceptance criterion is deterministic output plus structural equivalence, with any known layout differences documented in the build report and tests.

## 12. CLI milestone

Phase 1 exposes:

```text
rommod init <game.nds> <project-dir>
rommod inspect <game.nds-or-project>
rommod extract <project-dir>
rommod build <project-dir>
rommod verify <game.nds-or-project>
rommod patch <project-dir> --format bps|ips|xdelta
```

`init` writes the project manifest with the source SHA-256. `inspect` is read-only. `extract`, `build`, and `patch` require a project. `verify` can validate either a standalone ROM or a project's configured output.

## 13. External tool discovery

External binaries are resolved in this order:

1. explicit project/tool configuration;
2. environment/configured toolkit path;
3. system `PATH`.

The resolved executable path and version are recorded in build reports. Missing optional patch tools affect only the requested patch format. Missing armips causes an error only if the project contains an armips change.

No external source tree is vendored into the toolkit during Phase 1.

## 14. Error model

Public operations use typed toolkit exceptions rooted at `RomModError`.

Initial categories:

- `ManifestError`;
- `SourceMismatchError`;
- `RomValidationError`;
- `TargetNotFoundError`;
- `PatchMismatchError`;
- `AddressResolutionError`;
- `ExternalToolError`;
- `BuildError`.

CLI commands translate these into concise diagnostics and non-zero exit codes. Library users receive the structured exception.

## 15. Testing strategy

### Unit tests

Cover:

- manifest parsing and path containment;
- SHA-256 identity checks;
- byte-patch expected-byte enforcement;
- address/file-offset mapping;
- external command construction and failure translation;
- metadata normalization.

### Synthetic NDS fixtures

Tests should prefer programmatically-created or redistributable synthetic fixtures rather than copyrighted commercial ROMs. A tiny valid/near-minimal NDS fixture will exercise load/save and mutation paths.

### Integration tests

Cover:

1. untouched load -> save -> reload;
2. NitroFS file replacement -> rebuild -> reload -> verify replacement;
3. ARM9 byte patch -> rebuild -> verify bytes;
4. overlay byte patch -> rebuild -> verify bytes;
5. armips patch when armips is available;
6. BPS/IPS/xdelta generation when each backend is available;
7. deterministic repeated builds from the same source and manifest.

Tests requiring optional external tools are skipped with an explicit reason when the tool is unavailable; core NDS rebuild tests are never optional.

## 16. First implementation boundary

The first implementation plan should deliver the smallest vertical slice that proves the architecture:

1. Python package and CLI shell;
2. project manifest/init;
3. source hashing;
4. NDS load/inspect through ndspy;
5. NitroFS extraction/replacement;
6. ARM9/ARM7 and overlay extraction;
7. exact byte patches with expected-byte guards;
8. NDS rebuild and structural verification;
9. build report;
10. tests for the above.

Armips execution is the immediate next slice after the base rebuild path passes. Patch-file generation follows armips integration. Keystone, Unicorn, code-cave discovery, hooks/trampolines, compiled C injection, symbol-aware patching, and PSP support are explicitly outside this first implementation boundary.

## 17. Acceptance criteria

The NDS foundation is ready for advanced code modification when all of the following are true:

- `rommod init` creates a valid project with a locked source hash;
- `rommod inspect` reports normalized NDS metadata without modifying the ROM;
- `rommod extract` exports ARM binaries, overlays, NitroFS, and metadata;
- a declared NitroFS replacement rebuilds correctly;
- guarded byte patches work on ARM9/ARM7 and overlays;
- incorrect expected bytes abort the build;
- output is written only after validation succeeds;
- rebuilt output parses through a fresh NDS loader instance;
- repeated identical builds are deterministic under the same tool versions;
- automated tests use no proprietary commercial ROM data;
- the original source ROM remains unchanged.

Once these criteria pass, the next design/implementation phase can safely add armips-driven ARM/Thumb patches and then symbol-aware injection.
