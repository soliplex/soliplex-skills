"""Release manifest schema shared by the publishing workflow and clients.

Every published skill build carries a small JSON manifest describing the
artifact. For a software/tagged release it is attached as ``version.json``;
for a rolling build it is also published as ``latest.json`` under the
``…-latest`` pointer tag so a single request resolves "what is newest?".

The two files have an identical shape -- this module is its one definition.

.. note::

   **Proposed API / not yet implemented.** This is a design stub extracted
   from the per-repo workflows (the ``jq -n '{tag, source_commit, generated,
   sha256, asset_url}'`` step) and from ``skill_versions.py`` /
   ``apply.py``'s pointer parsing. Method bodies raise
   :class:`NotImplementedError`.
"""

from __future__ import annotations

import dataclasses
from collections import abc


@dataclasses.dataclass(frozen=True)
class ReleaseManifest:
    """A published skill build's ``version.json`` / ``latest.json`` payload.

    Attributes:
        tag: The release tag the asset lives under (rolling, e.g.
            ``docs-2026.05.29-cc9a290f``; or tagged, e.g. ``v0.68`` for a
            repo-coupled skill or ``soliplex-docs-v0.68`` for an
            independently-versioned one).
        source_commit: Short (7-char) commit the build was assembled from --
            the same value stamped into ``SKILL.md``'s
            ``metadata.source_commit``. This is how a client decides whether
            an installed skill matches a published one.
        generated: ISO date (``YYYY-MM-DD``) the build was produced.
        sha256: Hex digest of the asset tarball, for download verification.
        asset_url: Direct download URL of the asset tarball.
    """

    tag: str
    source_commit: str
    generated: str
    sha256: str
    asset_url: str

    @classmethod
    def from_json(cls, raw: str | bytes | abc.Mapping[str, object]) -> "ReleaseManifest":
        """Parse a manifest from JSON text/bytes or an already-decoded mapping."""
        raise NotImplementedError

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize to the canonical JSON written by the publishing workflow."""
        raise NotImplementedError
