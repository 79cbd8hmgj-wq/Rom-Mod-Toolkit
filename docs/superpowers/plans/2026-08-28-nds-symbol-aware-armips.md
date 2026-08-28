# NDS Symbol-Aware armips Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Allow armips changes to import component-aware symbols from NDS analysis output and use those names safely in ARM/Thumb assembly fragments.

**Architecture:** A toolkit-owned symbol model mirrors the stable fields already emitted by the NDS Disassembly Toolkit (`component`, runtime `address`, component-relative `offset`, `name`, `kind`, `instruction_set`, confidence/evidence). Each `ArmipsChange` may point to one symbol JSON file and optionally map a source component name to the selected ROM target. Before invoking armips, the adapter validates that every imported symbol belongs to the selected target's mapped runtime region and emits mode-aware armips label directives into the generated wrapper.

**Tech Stack:** Python 3.10+, JSON, ndspy 4.2.0, armips 0.11-compatible CLI, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-nds-modification-foundation-design.md`

## Global Constraints

- Symbol identity remains component-aware; runtime address alone is never a unique NDS overlay identity.
- Imported symbol files accept either a raw JSON array or `{ "symbols": [...] }`.
- Default source component is the armips target string; `symbol_component` explicitly maps arbitrary NDS-analysis component names.
- Imported symbols must have safe armips identifier names; unsafe names fail rather than being silently rewritten.
- A symbol imported for a target must have an address and offset consistent with that target's uncompressed runtime region.
- ARM symbols emit `.definearmlabel`; Thumb symbols emit `.definethumblabel`; neutral/data symbols emit `.definelabel`.
- Duplicate symbol names within the selected component fail closed.
- Symbol imports do not allow cross-component guessing for overlays with overlapping runtime addresses.
- Existing source-ROM protection, fixed-size armips target, rebuild validation, and atomic-output guarantees remain unchanged.

### Task 1: Symbol file model and loader

- [x] Write failing tests for list/object JSON forms, component-aware duplicate addresses, malformed records, and lookup.
- [x] Implement immutable `ImportedSymbol`/`ImportedSymbolTable` and strict JSON parsing.
- [x] Verify focused tests and full suite.

### Task 2: Manifest linkage

- [x] Add failing round-trip tests for `ArmipsChange.symbol_file` and optional `symbol_component`.
- [x] Extend strict manifest parsing/serialization without changing existing manifests.
- [x] Verify focused tests and full suite.

### Task 3: Mode-aware armips imports

- [x] Add real-armips tests using a symbolic `.org` and component mapping.
- [x] Validate imported names, duplicates, address range, and offset consistency.
- [x] Emit `.definearmlabel`, `.definethumblabel`, or `.definelabel` before the fragment include.
- [x] Confirm overlapping overlay addresses do not cross component boundaries.
- [x] Run complete suite with the compiled uploaded armips binary.

### Task 4: Documentation and smoke verification

- [x] Document the interchange JSON fields and component mapping.
- [x] Run `compileall`, full pytest, and a manual symbolic ARM9 patch smoke test.
