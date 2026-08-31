# NDS Patch Distribution

## Completed behavior

Rom Mod Toolkit now produces verified distributable patches from a source-locked project build:

```bash
rommod patch my-mod --format bps
rommod patch my-mod --format ips
rommod patch my-mod --format xdelta
```

An optional project-relative output path may be supplied:

```bash
rommod patch my-mod --format bps --output dist/release.bps
```

Without `--output`, the patch name is derived from the configured ROM output. For example, `build/output/game-modded.nds` becomes `build/output/game-modded.bps`.

## Safety and reproducibility contract

Patch creation never treats an existing output ROM as authoritative. The command:

1. Loads `rommod.yaml`.
2. Resolves the configured source ROM and verifies its locked SHA-256.
3. Rebuilds the modification project through the normal guarded build pipeline.
4. Creates the requested patch in `build/work/patch/<format>/`.
5. Applies that temporary patch back to the verified source ROM.
6. Requires the decoded result to match the freshly rebuilt target by size and SHA-256.
7. Atomically publishes the patch only after that verification succeeds.
8. Writes `reports/patch-<format>.json` with source, target, and patch hashes plus tool/version metadata.

A failed build, encoder invocation, decoder invocation, or byte-equivalence check prevents publication of the requested patch.

## Formats and tools

### BPS and IPS

BPS and IPS use Floating IPS (`flips`). BPS creation/application uses exact mode so the source/target identity checks performed by Flips remain enabled.

Tool resolution order is:

1. `tools.flips` in `rommod.yaml`;
2. `ROMMOD_FLIPS`;
3. `flips` on `PATH`.

Example:

```yaml
tools:
  flips: /path/to/flips
```

### xdelta

xdelta patches use the `xdelta3` CLI and are verified by decoding against the same locked source.

Tool resolution order is:

1. `tools.xdelta3` in `rommod.yaml`;
2. `ROMMOD_XDELTA3`;
3. `xdelta3` on `PATH`.

Example:

```yaml
tools:
  xdelta3: /path/to/xdelta3
```

The patching implementation lives under `src/rommod/patching/` rather than the NDS platform adapter. That keeps distribution reusable for later platform adapters such as PSP without making NDS responsible for generic binary-diff behavior.

## Report

A successful BPS build produces a report such as:

```json
{
  "format": "bps",
  "output": "build/output/game-modded.bps",
  "patch_sha256": "...",
  "patch_size": 1234,
  "source_sha256": "...",
  "target_sha256": "...",
  "verified": true,
  "build_report": "reports/build.json",
  "tool": {
    "path": "/path/to/flips",
    "version": "..."
  }
}
```

Equivalent reports are written for IPS and xdelta.

## Verification

The final functional implementation was verified in GitHub Actions at commit `08d711b7829d46fc9518bf35424988f95d354973`.

The clean Ubuntu job built and exercised real copies of:

- armips;
- Floating IPS;
- xdelta3;
- Clang;
- LLD;
- llvm-objcopy.

Python byte-compilation succeeded and the complete suite finished with:

```text
124 passed in 4.60s
```

The patch integration tests create and re-apply real BPS, IPS, and xdelta patches and require byte-equivalent decoded targets.
