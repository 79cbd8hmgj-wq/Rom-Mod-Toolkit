"""Project initialization and source verification."""

from __future__ import annotations

import os
from pathlib import Path

from rommod.core.hashes import sha256_file
from rommod.errors import ManifestError, SourceMismatchError
from rommod.projects.manifest import OutputConfig, ProjectManifest, SourceConfig, write_manifest


_PROJECT_DIRS = (
    "patches",
    "asm",
    "files",
    "build/extracted",
    "build/work",
    "build/output",
    "reports",
)


def init_project(source_rom: Path, project_dir: Path) -> ProjectManifest:
    source = Path(source_rom).resolve()
    project = Path(project_dir).resolve()
    if not source.is_file():
        raise ManifestError(f"Source ROM does not exist: {source}")
    project.mkdir(parents=True, exist_ok=True)
    for relative in _PROJECT_DIRS:
        (project / relative).mkdir(parents=True, exist_ok=True)

    source_ref = os.path.relpath(source, start=project)
    output_name = f"{source.stem}-modded.nds"
    manifest = ProjectManifest(
        schema_version=1,
        platform="nds",
        source=SourceConfig(rom=source_ref, sha256=sha256_file(source)),
        output=OutputConfig(rom=f"build/output/{output_name}"),
        changes=(),
    )
    write_manifest(project, manifest)
    return manifest


def resolve_source(project_dir: Path, manifest: ProjectManifest) -> Path:
    project = Path(project_dir).resolve()
    configured = Path(manifest.source.rom)
    return configured.resolve() if configured.is_absolute() else (project / configured).resolve()


def verify_source(project_dir: Path, manifest: ProjectManifest) -> Path:
    source = resolve_source(project_dir, manifest)
    if not source.is_file():
        raise SourceMismatchError(f"Configured source ROM is missing: {source}")
    actual = sha256_file(source)
    if actual != manifest.source.sha256:
        raise SourceMismatchError(
            f"Source ROM SHA-256 mismatch: expected {manifest.source.sha256}, got {actual}"
        )
    return source
