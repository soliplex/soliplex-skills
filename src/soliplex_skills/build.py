"""Assemble, stamp, and validate a skill into a distribution directory.

This is the build half of the release pipeline, generalizing the per-repo
``build_skill.py`` / ``build_skills.py`` / ``generate_docs_skill.py`` scripts:
copy a skill's source tree into ``dist/<name>/``, stamp its ``SKILL.md`` with
the source commit, and validate it with the agent-skills reference tool. The
CI workflow then packages ``dist/<name>/`` into release assets.

.. note::

   **Proposed API / not yet implemented.** Function bodies raise
   :class:`NotImplementedError`.
"""

from __future__ import annotations

from pathlib import Path


def discover_skills(skills_dir: Path) -> list[str]:
    """Return the names of every skill directory under *skills_dir*.

    A skill directory is one containing a ``SKILL.md``. Useful for repos that
    ship several skills (e.g. ``soliplex-concierge``).
    """
    raise NotImplementedError


def git_head_commit(repo_dir: Path) -> str | None:
    """Return *repo_dir*'s current commit SHA, or ``None`` if unavailable."""
    raise NotImplementedError


def build_skill(
    name: str,
    *,
    src: Path,
    dist: Path,
    commit: str | None = None,
    validate: bool = True,
) -> Path:
    """Assemble, stamp, and validate skill *name* into ``dist/<name>/``.

    Copies ``src/<name>/`` to ``dist/<name>/`` (skipping ``__pycache__``),
    stamps ``SKILL.md`` with *commit* via
    :func:`soliplex_skills.metadata.stamp_source_commit` (defaulting to the
    repo's git HEAD when ``None``), and -- when *validate* -- runs the
    agent-skills validator. Returns the built ``dist/<name>/`` path.
    """
    raise NotImplementedError
