# Source Intelligence Layer Design

## Goal

Add a repository-level semantic analysis and validated source-editing layer above Rom Mod Toolkit's existing ROM engineering infrastructure so repetitive game-data work can be indexed, analyzed, changed, and audited without binary escalation when the relevant behavior is already represented in source files.

## Scope

The first production slice targets Pokémon decomp-style repositories while keeping the framework game-agnostic. It must be able to:

- index structured repository data without modifying the repository;
- represent cross-file entities and relationships in a normalized in-memory model;
- analyze Pokémon species, evolutions, stats, abilities, learnsets, move properties, and TM/HM compatibility;
- detect progression defects such as post-evolution payoff gaps, evolution-delayed moves, reminder-only role moves, long STAB gaps, and physical/special role mismatches;
- accept a locked YAML change ledger for supported learnset operations;
- validate all requested edits before writing any file;
- apply changes atomically from the ledger;
- emit a machine-readable audit report and human-readable diff summary;
- remain separate from the NDS binary/rebuild layer so source-only work does not require ROM extraction or assembly tooling.

The first milestone is successful when the toolkit can reproduce the useful source-level findings from the C3D2 Persian/Primeape/Poliwrath/Golem/Rapidash block and can safely execute an equivalent locked learnset ledger.

## Architecture

The new subsystem is split into a generic repository-analysis layer and domain adapters.

```text
src/rommod/
├── analysis/
│   ├── __init__.py
│   ├── repository.py
│   ├── index.py
│   └── report.py
├── domains/
│   ├── __init__.py
│   └── pokemon/
│       ├── __init__.py
│       ├── models.py
│       ├── discovery.py
│       ├── loader.py
│       ├── analyzer.py
│       ├── ledger.py
│       └── editor.py
└── cli.py
```

`analysis/` owns game-independent concepts: repository roots, normalized index metadata, deterministic report writing, and common validation errors. `domains/pokemon/` owns assumptions about Pokémon decomp directory layouts and schemas.

The existing `platforms/nds/`, `projects/`, and `patching/` packages are not modified except for CLI integration. Source intelligence is intentionally usable without an NDS ROM project.

## Repository discovery

The Pokémon adapter targets repositories with species JSON under:

```text
res/pokemon/*/data.json
```

The adapter must discover actual files rather than assume a fixed National Dex list. Species identity defaults to the parent directory name and may be overridden by explicit name fields if the source schema provides them.

Related move/evolution/TM data may vary by decomp. The loader therefore uses schema probes rather than one hard-coded monolithic parser. Unsupported or missing structures are reported explicitly; they are not silently guessed.

Discovery is read-only and deterministic. Paths are stored relative to the repository root.

## Normalized model

The first slice defines normalized immutable records sufficient for analysis:

- `SpeciesRecord`: identifier, display name, source path, types, six base stats, abilities, level-up moves, evolution targets/sources when discoverable.
- `LearnsetEntry`: level and move identifier.
- `MoveRecord`: identifier, display name, type, category, power, accuracy, PP when discoverable.
- `EvolutionRecord`: source species, target species, method, level when discoverable.
- `RepositoryIndex`: repository root, indexed species mapping, move mapping, evolution records, warnings.

Unknown optional fields remain `None`. Required fields missing from a file produce a validation error naming the source path and field.

## Pokémon analysis rules

The analyzer returns facts and flags. It does not automatically redesign a species.

Initial rules:

1. **Post-evolution payoff gap** — report the number of levels from a level-based evolution to the evolved species' next natural move.
2. **Evolution-delayed move** — when a pre-evolution learns a move at a lower level than its evolved form, report the delay.
3. **Reminder-only move** — report level-1 moves separately from normal progression so role-defining utility trapped in the reminder pool is visible.
4. **STAB progression gap** — using move type/category data when available, report unusually long natural-level gaps between damaging same-type moves. The report exposes the raw interval; policy thresholds are configurable and default to 10 levels.
5. **Physical/special alignment** — compare Attack vs. Special Attack with natural damaging STAB categories and report when the stronger offensive stat has no corresponding natural STAB option in a configurable post-evolution window.

Each flag includes a stable code, severity, species, source evidence, and human-readable explanation.

The analyzer must not infer move power/category/type when move data is absent. It reports reduced-confidence analysis through warnings instead.

## CLI

Add a top-level `analyze` command with a Pokémon domain selector:

```bash
rommod analyze pokemon <repository> Persian Primeape Poliwrath Golem Rapidash
```

Output is JSON by default so later automation can consume it. `--text` produces a compact human-readable report.

Add a source-ledger command:

```bash
rommod source-apply pokemon <repository> c3d2.yaml --dry-run
rommod source-apply pokemon <repository> c3d2.yaml
```

`--dry-run` is the default-safe authoring path and prints the exact proposed operations without writing files.

## Locked learnset ledger

The first supported ledger schema is deliberately narrow:

```yaml
schema_version: 1
domain: pokemon
changes:
  persian:
    learnset:
      move:
        Switcheroo: 29
  primeape:
    learnset:
      replace:
        - level: 28
          move: Rage
          with:
            level: 29
            move: Brick Break
  poliwrath:
    learnset:
      add:
        - [36, Brick Break]
        - [40, Riptide Rush]
        - [46, Belly Drum]
  golem:
    learnset:
      add:
        - [35, Rock Slide]
  rapidash:
    learnset:
      remove:
        - [40, Fury Attack]
      set:
        Blaze Kick: 41
        Bounce: 42
        Flare Blitz: 46
```

Semantics:

- `move`: move an existing move to a new level; it fails if the move is absent or duplicated ambiguously.
- `replace`: replace one exact `(level, move)` entry with another.
- `add`: add an exact entry; it fails if the exact entry already exists.
- `remove`: remove an exact entry; it fails if absent.
- `set`: ensure a move exists exactly once at the requested level, relocating an existing occurrence if necessary.

All species and move identifiers are matched case-insensitively against normalized identifiers but reports preserve source spelling.

## Validation and writes

Ledger application is two-phase:

1. Parse and validate the entire ledger against an in-memory index.
2. Build all edited JSON documents in memory, validate resulting learnsets, then write files atomically.

No file is written if any requested operation fails.

Validation rejects:

- unknown species;
- unknown move names when a move index is available;
- ambiguous duplicate move occurrences for `move`;
- duplicate exact level/move entries after editing;
- malformed ledger operations;
- source files that changed between read and write, detected by SHA-256 content hashes.

JSON formatting preserves the repository file's indentation style when practical. Key order is preserved by Python's insertion-ordered dictionaries; unrelated fields are not rewritten semantically.

## Reports

Analysis returns a serializable structure with:

- repository path;
- indexed counts;
- selected species;
- normalized facts;
- analysis flags;
- warnings.

Ledger execution writes `reports/source-apply-<ledger-stem>.json` under the repository by default, unless `--report` supplies another path. The report contains:

- ledger SHA-256;
- source file hashes before and after;
- validated operations;
- modified files;
- per-species before/after learnset entries;
- dry-run/applied status.

The toolkit never creates or modifies binary ROM data during these commands.

## Error handling

All user-facing failures use existing `RomModError` subclasses so the CLI continues to emit concise `error: ...` messages and exit code 2.

Schema errors name the offending relative file path and field/operation. The subsystem fails closed rather than filling missing game data from external knowledge.

## Testing

Tests use synthetic repositories only. No commercial ROM or copyrighted game repository is required.

Coverage must include:

- repository discovery;
- normalized species/learnset parsing;
- deterministic indexing;
- each analysis flag with minimal fixtures;
- graceful warnings when optional move metadata is missing;
- each ledger operation;
- whole-ledger rollback on one invalid operation;
- dry-run immutability;
- atomic write/hash guard behavior;
- CLI JSON output and exit codes;
- a synthetic C3D2 fixture that reproduces the key Persian, Primeape, and Rapidash timing findings and applies the five-species ledger.

Existing 129 NDS tests must remain green.

## Non-goals for this patch

- automatic balance decisions or AI-authored redesigns;
- binary/disassembly analysis;
- automatic inference of undocumented engine behavior;
- generalized mutation of arbitrary JSON fields;
- C++/emulator enhancements;
- support for every Pokémon decomp schema in the first release;
- other game-domain adapters.

Those can build on the normalized analysis/domain boundary after this slice proves the workflow.