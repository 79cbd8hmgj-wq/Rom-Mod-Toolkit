# NDS armips Patching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe armips-backed ARM/Thumb modification jobs for NDS ARM9, ARM7, and overlay targets while preserving the Phase 1 source-lock, mutation-accounting, rebuild, and validation guarantees.

**Architecture:** `ArmipsChange` is a manifest mutation handled by an NDS assembler adapter. The adapter owns the output file: it copies exactly one selected code target into an isolated build job, generates an architecture-correct wrapper, includes a single user assembly fragment, invokes a resolved armips executable, rejects target resizing, and returns patched bytes plus optional symbol output to the existing rebuild pipeline. User fragments cannot open/create/close/include other files in this first slice.

**Tech Stack:** Python 3.10+, ndspy 4.2.0, armips 0.11-compatible CLI, PyYAML, pytest, subprocess/pathlib/shutil.

**Spec:** `docs/superpowers/specs/2026-08-28-nds-modification-foundation-design.md`

## Global Constraints

- Never allow armips to write the source ROM.
- armips runs only against a copied ARM9/ARM7/overlay target under `build/work/`.
- Supported targets are `arm9`, `arm7`, `overlay9:<id>`, and `overlay7:<id>`.
- CPU-address mapping is allowed only for uncompressed code targets.
- ARM9 uses armips `.nds`; ARM7 uses `.gba` plus `.arm`; fragments may switch between `.arm` and `.thumb`.
- Fragment file-ownership directives are rejected in this slice: open/openfile/create/createfile/close/closefile/loadelf/include/headersize and architecture-selection directives.
- A patched target must remain exactly the same serialized size.
- Missing/failed armips execution raises `ExternalToolError` and does not write the configured ROM output.
- Optional symbol output is materialized only after the rebuilt ROM has passed validation.
- External tool resolution order: manifest `tools.armips`, `ROMMOD_ARMIPS`, then `PATH`.
- Build reports record armips path/version when armips is used.

---

### Task 1: Manifest and tool resolution

**Files:** modify `manifest.py`; create `core/subprocesses.py`; tests `test_armips_manifest.py`, `test_subprocesses.py`.

- [ ] Add failing tests for `tools.armips`, `ArmipsChange`, YAML round-trip, configured/env/PATH resolution, and missing tool.
- [ ] Run focused tests and verify failure from missing symbols/modules.
- [ ] Implement frozen `ToolsConfig`/`ArmipsChange` and strict parsing/serialization.
- [ ] Implement executable resolution plus captured subprocess execution.
- [ ] Run focused tests and full suite.

### Task 2: Isolated NDS armips job

**Files:** create `platforms/nds/assembler.py`; tests `test_armips.py` and real integration coverage.

- [ ] Write failing tests for forbidden directives, target selection, ARM9 real patch, symbols, ARM7 architecture, and missing tool.
- [ ] Generate isolated wrapper scripts and target copies under `build/work/armips/<index>/`.
- [ ] Invoke armips with `-erroronwarning`, optional `-sym`, and `-temp` diagnostics.
- [ ] Reject nonzero exit, missing target, and target size changes.
- [ ] Return tool/version/symbol data without writing final project artifacts yet.

### Task 3: Build-pipeline integration

**Files:** modify `projects/build.py`; integration `test_build_armips.py`.

- [ ] Apply `ArmipsChange` in manifest order and include its target in post-rebuild verification.
- [ ] Commit patched bytes back into the in-memory NDS target.
- [ ] Atomically write requested symbol files only after rebuilt ROM validation succeeds.
- [ ] Record armips mutation metadata and tool path/version in `reports/build.json`.
- [ ] Verify failed assembler jobs do not produce the configured output.

### Task 4: CLI/docs/final verification

**Files:** update `README.md`; retain existing CLI surface (`rommod build`).

- [ ] Document armips discovery, fragment contract, target syntax, CPU-address usage, ARM/Thumb mode changes, and symbol output.
- [ ] Build the uploaded armips source locally when possible and run real integration tests with `ROMMOD_ARMIPS` pointed at that binary.
- [ ] Run `compileall` and the complete pytest suite.
- [ ] Run a manual synthetic project smoke test with an actual armips fragment and verify patched bytes plus symbols in the rebuilt ROM.
