"""``list`` / ``diff`` / ``upgrade`` for a published filesystem skill.

This consolidates the ~575-line ``skill_versions.py`` that is currently
vendored verbatim into every skill (``soliplex-docs``,
``soliplex-template``, ``soliplex-concierge-{installer,room,admin}``). Those
copies differ only in a handful of constants and one behavioral toggle; both
are captured here by :class:`SkillSpec`, so the vendored script collapses to a
thin shim that builds a ``SkillSpec`` and delegates to :class:`SkillVersions`.

.. note::

   **Proposed API / not yet implemented.** Method bodies raise
   :class:`NotImplementedError`.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Literal

#: How ``diff`` compares an installed skill against a published one.
#:
#: * ``"tree"``       -- the whole skill tree (SKILL.md, scripts/, assets/,
#:   references/). Used by ``soliplex-template`` and the concierge skills.
#: * ``"references"`` -- only the ``references/`` Markdown. Used by
#:   ``soliplex-docs``, whose payload is documentation.
CompareScope = Literal["tree", "references"]


@dataclasses.dataclass(frozen=True)
class SkillSpec:
    """Everything that distinguishes one published skill from another.

    These are exactly the constants that differ between the vendored
    ``skill_versions.py`` copies today.

    Attributes:
        owner: GitHub repository owner (e.g. ``"soliplex"``).
        repo: GitHub repository name the skill is released from.
        skill_name: The skill's directory / SKILL.md name.
        asset_tarball: Release asset filename (e.g.
            ``"soliplex-docs-skill.tar.gz"``).
        pointer_tag: The ``…-latest`` tag carrying ``latest.json`` (e.g.
            ``"docs-latest"``).
        rolling_re: Pattern identifying rolling-build tags (e.g.
            ``^docs-\\d{4}\\.\\d{2}\\.\\d{2}-[0-9a-f]+$``). Tags that do not
            match are treated as tagged releases -- whether they live on the
            repo's own ``v…`` tag (a repo-coupled skill) or under the skill's
            own ``<skill>-vX.Y.Z`` namespace (an independently-versioned
            skill) is irrelevant to the client; both are just "release" tags
            carrying this skill's :attr:`asset_tarball`.
        compare_scope: See :data:`CompareScope`.
        pointer_manifest: Manifest filename under the pointer tag.
    """

    owner: str
    repo: str
    skill_name: str
    asset_tarball: str
    pointer_tag: str
    rolling_re: re.Pattern[str]
    compare_scope: CompareScope = "tree"
    pointer_manifest: str = "latest.json"


class SkillVersions:
    """Operations over a published skill's GitHub releases.

    Wraps a :class:`SkillSpec` and offers the three subcommands the vendored
    script exposes. ``target`` arguments accept a concrete tag or the literal
    ``"latest"``, which is expanded via the skill's pointer manifest.
    """

    def __init__(self, spec: SkillSpec):
        self.spec = spec

    def list(self, *, kind: Literal["rolling", "release"] | None = None) -> list[dict]:
        """Return skill-bearing releases, newest first (excluding the pointer).

        Each entry carries ``tag``, ``date``, ``kind``, ``commit`` and
        ``prerelease``. *kind* optionally filters to rolling builds or tagged
        releases.
        """
        raise NotImplementedError

    def diff(
        self,
        installed_path: Path,
        target: str = "latest",
        *,
        name_only: bool = False,
    ) -> int:
        """Show how the skill at *installed_path* differs from *target*.

        Honors :attr:`SkillSpec.compare_scope`. Returns ``0`` when identical,
        ``1`` when differences were reported (a process-style status code).
        """
        raise NotImplementedError

    def upgrade(
        self,
        installed_path: Path,
        target: str = "latest",
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> int:
        """Download *target* and install it over *installed_path*.

        The tarball's sha256 is verified against the manifest when known, and
        files are replaced in place -- directories removed first -- so files
        deleted upstream do not linger. A no-op when the installed
        ``source_commit`` already matches *target* unless *force* is set;
        *dry_run* reports the plan without writing. Returns a status code.
        """
        raise NotImplementedError
