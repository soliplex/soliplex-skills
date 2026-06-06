"""Smoke tests for the library skeleton.

These assert the proposed public surface exists and imports cleanly, and that
the as-yet-unimplemented entry points fail loudly (``NotImplementedError``)
rather than silently returning ``None``. They are the executable counterpart
to the "proposed / not yet implemented" note throughout the docs: once a stub
is implemented, the matching ``pytest.raises`` here should be replaced by a
real behavioral test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Client code imports the submodules directly -- the package has no
# re-exporting ``__init__``.
from soliplex_skills import (
    build,
    cli,
    install,
    manifest,
    metadata,
    releases,
    versions,
)


def test_submodules_expose_their_public_names():
    # setup / execute
    surface = {
        manifest: ["ReleaseManifest"],
        metadata: ["read_source_commit", "stamp_source_commit"],
        releases: ["list_releases", "classify", "read_pointer"],
        versions: ["SkillSpec", "SkillVersions"],
        build: ["discover_skills", "build_skill"],
        install: ["PublishedSkill", "download_skill"],
        cli: ["main"],
    }

    # assertions
    for module, names in surface.items():
        for name in names:
            assert hasattr(module, name), f"{module.__name__}.{name}"


def test_dataclasses_construct():
    # setup
    spec = versions.SkillSpec(
        owner="soliplex",
        repo="soliplex",
        skill_name="soliplex-docs",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
        rolling_re=re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"),
        compare_scope="references",
    )

    # execute
    man = manifest.ReleaseManifest(
        tag="docs-2026.05.29-cc9a290f",
        source_commit="cc9a290",
        generated="2026-05-29",
        sha256="0" * 64,
        asset_url="https://example.invalid/a.tar.gz",
    )

    # assertions
    assert spec.compare_scope == "references"
    assert spec.pointer_manifest == "latest.json"
    assert man.tag.startswith("docs-")


@pytest.mark.parametrize(
    "call",
    [
        lambda: metadata.read_source_commit(Path("SKILL.md")),
        lambda: metadata.stamp_source_commit(Path("SKILL.md"), "abc1234"),
        lambda: releases.list_releases("soliplex", "soliplex"),
        lambda: build.discover_skills(Path("skills")),
        lambda: cli.main([]),
    ],
    ids=["read_commit", "stamp_commit", "list_releases", "discover_skills", "cli"],
)
def test_stubs_raise_not_implemented(call):
    # execute / assertions
    with pytest.raises(NotImplementedError):
        call()


def test_skill_versions_methods_raise_not_implemented():
    # setup
    spec = versions.SkillSpec(
        owner="soliplex",
        repo="soliplex-template",
        skill_name="soliplex-template",
        asset_tarball="soliplex-template-skill.tar.gz",
        pointer_tag="template-skill-latest",
        rolling_re=re.compile(r"^template-skill-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"),
    )
    sv = versions.SkillVersions(spec)

    # execute / assertions
    with pytest.raises(NotImplementedError):
        sv.list()


def test_published_skill_download_base_raises():
    # setup
    pub = install.PublishedSkill(
        name="soliplex-docs",
        owner="soliplex",
        repo="soliplex",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
    )

    # execute / assertions
    with pytest.raises(NotImplementedError):
        _ = pub.download_base
