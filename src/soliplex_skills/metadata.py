"""Read and stamp a skill's installed identity in ``SKILL.md`` frontmatter.

A built skill records the commit it was assembled from as
``metadata.source_commit`` in its ``SKILL.md`` YAML frontmatter. That value is
the skill's installed identity: the publishing workflow stamps it at build
time, and ``versions``/``releases`` read it back to tell which published build
is installed.

This module consolidates two functions copy-pasted across the sibling repos:

* ``stamp_source_commit`` -- identical in
  ``soliplex-template/scripts/build_skill.py`` and
  ``soliplex-concierge/scripts/build_skills.py``.
* the ``_COMMIT_RE`` / ``_commit_of`` reader embedded in every vendored
  ``skill_versions.py``.

.. note::

   **Proposed API / not yet implemented.** Function bodies raise
   :class:`NotImplementedError`.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Matches ``source_commit: "abc1234"`` (quotes optional) on a frontmatter line.
COMMIT_RE = re.compile(r'^\s*source_commit:\s*"?([0-9a-fA-F]+)"?\s*$')


def read_source_commit(skill_md: Path) -> str | None:
    """Return the 7-char ``source_commit`` recorded in *skill_md*, or ``None``.

    ``None`` is returned when the file is missing or carries no
    ``source_commit`` entry (e.g. the tracked source SKILL.md, which is left
    unstamped -- only built copies carry the commit).
    """
    raise NotImplementedError


def stamp_source_commit(skill_md: Path, commit: str) -> None:
    """Record ``metadata.source_commit: "<commit>"`` in *skill_md*'s frontmatter.

    Idempotent: a SKILL.md that already carries a ``source_commit`` is left
    untouched. The entry is inserted under an existing ``metadata:`` block if
    present, otherwise a new ``metadata:`` block is appended just before the
    closing ``---`` fence. Raises if the file has no YAML frontmatter to stamp.
    """
    raise NotImplementedError
