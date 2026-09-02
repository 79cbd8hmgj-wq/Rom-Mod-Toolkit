# Source Intelligence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a game-agnostic repository analysis framework plus a Pokémon source-data adapter that can index decomp data, detect progression defects, and atomically execute locked learnset ledgers.

**Architecture:** Keep repository indexing/reporting under `rommod.analysis` and Pokémon-specific schema knowledge under `rommod.domains.pokemon`. The CLI calls domain APIs directly and leaves all existing NDS ROM engineering paths untouched. Ledger writes are validate-first, all-or-nothing, and hash-guarded.

**Tech Stack:** Python 3.10+, standard library `json`, `dataclasses`, `hashlib`, `pathlib`, existing PyYAML dependency, pytest 8+.

**Spec:** `docs/superpowers/specs/2026-09-02-source-intelligence-design.md`

## Global Constraints

- Existing NDS behavior and all 129 baseline tests must remain green.
- Source intelligence must work without an NDS ROM project.
- Tests use only synthetic repositories.
- Unsupported source schema must fail explicitly or emit a warning; never fill gaps from external knowledge.
- No production code is written before the failing test for that behavior.
- Ledger execution validates every operation before the first write.
- Source files are protected by SHA-256 change detection between load and write.

---

### Task 1: Generic repository primitives

**Files:**
- Create: `src/rommod/analysis/__init__.py`
- Create: `src/rommod/analysis/repository.py`
- Create: `src/rommod/analysis/report.py`
- Test: `tests/analysis/test_repository.py`

**Interfaces:**
- Produces: `RepositorySnapshot(root: Path)`, `SourceDocument(relative_path: Path, data: dict, sha256: str, indent: int)`, `load_json_document(root: Path, path: Path) -> SourceDocument`, `write_json_document(snapshot: RepositorySnapshot, document: SourceDocument, new_data: dict) -> str`.

- [ ] **Step 1: Write failing tests for safe repository-relative JSON loading and SHA-256 capture.**

```python
from pathlib import Path
from rommod.analysis.repository import RepositorySnapshot, load_json_document


def test_load_json_document_captures_relative_path_hash_and_indent(tmp_path: Path):
    path = tmp_path / "res" / "pokemon" / "persian" / "data.json"
    path.parent.mkdir(parents=True)
    path.write_text('{\n  "name": "Persian"\n}\n', encoding="utf-8")

    snap = RepositorySnapshot(tmp_path)
    doc = load_json_document(snap.root, path)

    assert doc.relative_path.as_posix() == "res/pokemon/persian/data.json"
    assert doc.data["name"] == "Persian"
    assert len(doc.sha256) == 64
    assert doc.indent == 2
```

- [ ] **Step 2: Run `pytest tests/analysis/test_repository.py -q` and verify import/behavior failure.**
- [ ] **Step 3: Implement immutable snapshot/document dataclasses, root containment checks, JSON parsing, hash capture, and indentation detection.**
- [ ] **Step 4: Add a failing test proving writes abort when the source hash changed after load.**
- [ ] **Step 5: Implement atomic temp-file replacement with hash guard and return the new SHA-256.**
- [ ] **Step 6: Run the task tests and then `pytest -q`.**
- [ ] **Step 7: Commit with `feat: add repository source primitives`.**

### Task 2: Pokémon discovery and normalized models

**Files:**
- Create: `src/rommod/domains/__init__.py`
- Create: `src/rommod/domains/pokemon/__init__.py`
- Create: `src/rommod/domains/pokemon/models.py`
- Create: `src/rommod/domains/pokemon/discovery.py`
- Create: `src/rommod/domains/pokemon/loader.py`
- Test: `tests/domains/pokemon/test_loader.py`

**Interfaces:**
- Produces: immutable `LearnsetEntry`, `MoveRecord`, `EvolutionRecord`, `SpeciesRecord`, `RepositoryIndex`; `discover_species_files(root: Path) -> list[Path]`; `load_repository_index(root: Path) -> RepositoryIndex`.

- [ ] **Step 1: Write a failing synthetic fixture test that discovers `res/pokemon/*/data.json` in deterministic path order.**
- [ ] **Step 2: Implement discovery only; run the focused test green.**
- [ ] **Step 3: Write failing tests for the minimal supported species schema used by the current decomp workflow: name/identifier, types, six base stats, abilities, and level-up moves.**
- [ ] **Step 4: Implement normalization with case-folded identifiers while preserving display spelling and relative source path.**
- [ ] **Step 5: Add failing tests for malformed required fields producing a `RomModError` that names the relative source path.**
- [ ] **Step 6: Implement explicit validation failures and warnings collection for absent optional move/evolution metadata.**
- [ ] **Step 7: Run focused tests and full suite.**
- [ ] **Step 8: Commit with `feat: index pokemon source data`.**

### Task 3: Evolution and move metadata probes

**Files:**
- Modify: `src/rommod/domains/pokemon/loader.py`
- Modify: `src/rommod/domains/pokemon/models.py`
- Test: `tests/domains/pokemon/test_loader.py`

**Interfaces:**
- Extends: `load_repository_index(root)` with `moves` and `evolutions` when supported structures are present.

- [ ] **Step 1: Write failing tests for a synthetic move metadata directory and evolution records embedded in species JSON.**
- [ ] **Step 2: Implement schema probes that recognize the fixture schema without requiring move metadata to exist.**
- [ ] **Step 3: Write a failing test that missing move metadata leaves `moves == {}` and adds a warning instead of guessing categories or power.**
- [ ] **Step 4: Implement warnings and deterministic evolution relation assembly.**
- [ ] **Step 5: Run focused tests and full suite.**
- [ ] **Step 6: Commit with `feat: index pokemon move and evolution metadata`.**

### Task 4: Pokémon progression analyzer

**Files:**
- Create: `src/rommod/domains/pokemon/analyzer.py`
- Test: `tests/domains/pokemon/test_analyzer.py`

**Interfaces:**
- Produces: `AnalysisFlag(code, severity, species, evidence, message)`, `SpeciesAnalysis(species, facts, flags, warnings)`, `analyze_species(index: RepositoryIndex, species_ids: list[str], stab_gap_threshold: int = 10, alignment_window: int = 12) -> list[SpeciesAnalysis]`.

- [ ] **Step 1: Write a failing Persian fixture test that reports level-1/reminder moves separately from normal progression.**
- [ ] **Step 2: Implement reminder-pool facts only.**
- [ ] **Step 3: Write a failing Primeape fixture test for a level-based evolution followed by a long next-natural-move gap.**
- [ ] **Step 4: Implement post-evolution payoff gap calculation with raw level distance.**
- [ ] **Step 5: Write a failing Rapidash fixture test where Ponyta learns Bounce/Flare Blitz earlier than Rapidash.**
- [ ] **Step 6: Implement `evolution-delayed-move` flags by comparing shared move identifiers across an evolution edge.**
- [ ] **Step 7: Write failing tests for STAB-gap and physical/special alignment using synthetic move metadata.**
- [ ] **Step 8: Implement only those two rules, emitting warnings when move metadata is absent.**
- [ ] **Step 9: Run focused tests and full suite.**
- [ ] **Step 10: Commit with `feat: analyze pokemon progression`.**

### Task 5: Locked learnset ledger parser and dry-run executor

**Files:**
- Create: `src/rommod/domains/pokemon/ledger.py`
- Create: `src/rommod/domains/pokemon/editor.py`
- Test: `tests/domains/pokemon/test_ledger.py`

**Interfaces:**
- Produces: `Ledger`, `LearnsetOperation`, `load_ledger(path: Path) -> Ledger`, `plan_ledger(index: RepositoryIndex, ledger: Ledger) -> SourceApplyPlan`, `SourceApplyPlan.apply(dry_run: bool = True) -> SourceApplyReport`.

- [ ] **Step 1: Write failing parser tests for `move`, `replace`, `add`, `remove`, and `set`.**
- [ ] **Step 2: Implement strict schema-version/domain validation and immutable operation records.**
- [ ] **Step 3: Write failing dry-run tests proving every operation transforms in-memory learnsets correctly while source files remain byte-identical.**
- [ ] **Step 4: Implement operation planning against normalized species identifiers.**
- [ ] **Step 5: Add failing tests for unknown species, unknown move when move index exists, absent removal target, ambiguous move relocation, and duplicate exact entries.**
- [ ] **Step 6: Implement whole-ledger validation before producing a writable plan.**
- [ ] **Step 7: Run focused tests and full suite.**
- [ ] **Step 8: Commit with `feat: plan pokemon learnset ledgers`.**

### Task 6: Atomic ledger application and audit report

**Files:**
- Modify: `src/rommod/domains/pokemon/editor.py`
- Modify: `src/rommod/analysis/report.py`
- Test: `tests/domains/pokemon/test_editor.py`

**Interfaces:**
- `SourceApplyPlan.apply(dry_run=False)` writes all validated JSON changes and returns report fields `ledger_sha256`, `modified_files`, `before_hashes`, `after_hashes`, `operations`, `before_learnsets`, `after_learnsets`, `applied`.

- [ ] **Step 1: Write a failing test that applies two species edits and records before/after hashes and learnsets.**
- [ ] **Step 2: Implement staged serialization and atomic writes only after every file passes the pre-write hash guard.**
- [ ] **Step 3: Write a failing test where one source file changes after planning and verify zero files are modified.**
- [ ] **Step 4: Implement preflight hash verification for every target before the first replacement.**
- [ ] **Step 5: Write failing deterministic report JSON test.**
- [ ] **Step 6: Implement stable report serialization.**
- [ ] **Step 7: Run focused tests and full suite.**
- [ ] **Step 8: Commit with `feat: apply pokemon source ledgers atomically`.**

### Task 7: CLI integration

**Files:**
- Modify: `src/rommod/cli.py`
- Test: `tests/test_cli_source_intelligence.py`

**Interfaces:**
- Adds: `rommod analyze pokemon <repository> <species...> [--text] [--stab-gap-threshold N]`.
- Adds: `rommod source-apply pokemon <repository> <ledger> [--apply] [--report PATH]` where omission of `--apply` is dry-run.

- [ ] **Step 1: Write failing parser/CLI test for JSON analysis output.**
- [ ] **Step 2: Add nested `analyze pokemon` parser and JSON serialization.**
- [ ] **Step 3: Write failing CLI test for `source-apply` default dry-run and explicit `--apply`.**
- [ ] **Step 4: Add CLI wiring and concise text mode.**
- [ ] **Step 5: Verify `RomModError` still maps to exit code 2 for source-intelligence failures.**
- [ ] **Step 6: Run focused tests and full suite.**
- [ ] **Step 7: Commit with `feat: expose source intelligence CLI`.**

### Task 8: Synthetic C3D2 acceptance fixture and documentation

**Files:**
- Create: `tests/integration/test_source_intelligence_c3d2.py`
- Modify: `README.md`

**Interfaces:**
- Acceptance: one synthetic repository with Persian, Primeape, Poliwrath, Golem, Rapidash, Ponyta, Mankey, and the necessary move metadata reproduces the intended timing evidence and accepts the five-species ledger.

- [ ] **Step 1: Write failing end-to-end fixture asserting Persian reminder evidence, Primeape post-evolution gap, Rapidash evolution-delayed Bounce/Flare Blitz, and the planned five-species edits.**
- [ ] **Step 2: Fix only integration defects exposed by the acceptance test.**
- [ ] **Step 3: Apply the ledger in the fixture and assert the exact final levels for Switcheroo, Brick Break, Riptide Rush, Belly Drum, Rock Slide, Blaze Kick, Bounce, and Flare Blitz.**
- [ ] **Step 4: Document `analyze pokemon` and `source-apply pokemon` workflows plus source-only safety boundaries in README.**
- [ ] **Step 5: Run `python -m compileall -q src tests` and `pytest -q`. Expected: all pre-existing tests plus new source-intelligence tests pass.**
- [ ] **Step 6: Commit with `docs: document source intelligence workflow`.**

## Self-review

- Spec coverage: indexing, analysis, ledger planning, atomic writes, reports, CLI, and C3D2 acceptance are each mapped to a task.
- Placeholder scan: no TBD/TODO steps or unspecified implementation gaps remain.
- Type consistency: `RepositoryIndex`, `SpeciesAnalysis`, `Ledger`, `SourceApplyPlan`, and `SourceApplyReport` are introduced before downstream use.
- Scope: other game adapters and automatic balance decisions remain explicit non-goals.