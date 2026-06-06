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

import pytest

# Client code imports the submodules directly -- the package has no
# re-exporting ``__init__``.
from soliplex_skills import build
from soliplex_skills import cli
from soliplex_skills import install
from soliplex_skills import manifest
from soliplex_skills import metadata
from soliplex_skills import releases
from soliplex_skills import versions


def test_submodules_expose_their_public_names():
    surface = {
        manifest: ["ReleaseManifest"],
        metadata: ["read_source_commit", "stamp_source_commit"],
        releases: ["list_releases", "classify", "read_pointer"],
        versions: ["SkillSpec", "SkillVersions"],
        build: ["discover_skills", "build_skill"],
        install: ["PublishedSkill", "download_skill"],
        cli: ["main"],
    }

    for module, names in surface.items():
        for name in names:
            assert hasattr(module, name), f"{module.__name__}.{name}"


def test_dataclasses_construct():
    spec = versions.SkillSpec(
        owner="soliplex",
        repo="soliplex",
        skill_name="soliplex-docs",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
        rolling_re=re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"),
        compare_scope="references",
    )

    man = manifest.ReleaseManifest(
        tag="docs-2026.05.29-cc9a290f",
        source_commit="cc9a290",
        generated="2026-05-29",
        sha256="0" * 64,
        asset_url="https://example.invalid/a.tar.gz",
    )

    assert spec.compare_scope == "references"
    assert spec.pointer_manifest == "latest.json"
    assert man.tag.startswith("docs-")


# Not-yet-implemented entry points. As each phase lands, its lambda moves out
# of this list into a real behavioral test module; the remaining stubs must
# still fail loudly rather than silently returning ``None``.
@pytest.mark.parametrize(
    "call",
    [
        lambda: cli.main([]),
    ],
    ids=["cli"],
)
def test_stubs_raise_not_implemented(call):
    with pytest.raises(NotImplementedError):
        call()
