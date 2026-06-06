"""Download a published skill and extract it onto disk.

Where :mod:`soliplex_skills.versions` manages a skill that is *already*
installed (upgrading it in place), this module covers the first-time install:
resolve a published skill to an asset, download and verify it, and extract its
skill root. This generalizes the ``PublishedSkill`` dataclass and
``download_skill`` helper found in
``soliplex-concierge/.../installer/scripts/apply.py``.

.. note::

   The stack-editing helpers from ``apply.py`` (surgically wiring a skill into
   a target Soliplex stack's ``pyproject.toml`` / ``installation.yaml`` /
   rooms) are intentionally out of scope for now -- they belong in a later,
   installer-specific module.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from soliplex_skills import _archive
from soliplex_skills import releases
from soliplex_skills.versions import PointerUnavailable

_GITHUB = "https://github.com"


@dataclasses.dataclass(frozen=True)
class PublishedSkill:
    """A filesystem skill published as a GitHub-release tarball.

    Attributes:
        name: The skill's SKILL.md / directory name.
        owner: GitHub repository owner.
        repo: GitHub repository name.
        asset_tarball: Release asset filename.
        pointer_tag: The ``…-latest`` tag carrying the pointer manifest.
        pointer_manifest: Manifest filename under the pointer tag.
    """

    name: str
    owner: str
    repo: str
    asset_tarball: str
    pointer_tag: str
    pointer_manifest: str = "latest.json"

    @property
    def download_base(self) -> str:
        """Base URL for this repo's release-download assets."""
        return f"{_GITHUB}/{self.owner}/{self.repo}/releases/download"

    def asset_url(self, tag: str) -> str:
        """Direct download URL for this skill's asset under *tag*."""
        return f"{self.download_base}/{tag}/{self.asset_tarball}"

    def pointer_url(self) -> str:
        """URL of the ``…-latest`` pointer manifest."""
        return (
            f"{self.download_base}/{self.pointer_tag}/{self.pointer_manifest}"
        )


def download_skill(
    spec: PublishedSkill, version: str | None, dest: Path
) -> Path:
    """Download + extract *spec* into *dest*; return the extracted skill root.

    When *version* is ``None`` the skill's ``latest`` pointer is read (and its
    recorded sha256 verified); an explicit tag builds the asset URL by name.
    The returned path is the directory containing ``SKILL.md``.
    """
    if version is None:
        pointer = releases.read_pointer(spec.pointer_url())
        if pointer is None:
            raise PointerUnavailable(spec.pointer_tag)
        asset_url, sha256 = pointer.asset_url, pointer.sha256
    else:
        asset_url, sha256 = spec.asset_url(version), None

    extract_dir = _archive.download_and_extract(
        asset_url, dest, expected_sha256=sha256
    )
    return _archive.find_skill_root(extract_dir)
