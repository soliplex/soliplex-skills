"""Read and stamp a skill's build identity in ``SKILL.md`` frontmatter.

A built skill records, under its ``SKILL.md`` YAML frontmatter ``metadata``
table, the identity of the build:

- ``source_commit`` -- the 7-char commit the build was assembled from,
- ``generated`` -- the ISO build date, and
- ``version`` -- the published version (only for non-rolling builds).

The build step stamps these (:func:`stamp_metadata`) and ``versions`` /
``releases`` read ``source_commit`` back (:func:`read_source_commit`) to tell
which published build is installed.

Frontmatter is *parsed* through the shared ``skills_ref`` library, but the
*write* is a surgical text insertion: ``skills_ref`` ships no writer, and a
YAML round-trip reformats hand-authored frontmatter (re-wrapping/re-quoting
descriptions, re-indenting block scalars). Inserting only the new entries
leaves every other byte untouched.
"""

from __future__ import annotations

import pathlib

import skills_ref

#: ``metadata.*`` keys the build stamps, in canonical frontmatter order.
STAMP_KEYS = ("version", "source_commit", "generated")

#: Per-build volatile stamps normalized out of ``diff`` comparison. ``version``
#: is deliberately excluded -- a version change is a genuine difference.
VOLATILE_STAMP_KEYS = ("source_commit", "generated")


class MissingFrontmatterError(ValueError):
    """A ``SKILL.md`` had no YAML frontmatter to stamp."""

    def __init__(self, skill_md: pathlib.Path):
        super().__init__(f"{skill_md} has no YAML frontmatter to stamp")


def _read_metadata(skill_md: pathlib.Path) -> dict[str, str]:
    """Return *skill_md*'s parsed ``metadata`` table, or ``{}`` if unreadable.

    Delegates to :func:`skills_ref.read_properties`; an empty dict is returned
    when the SKILL.md is missing or its frontmatter cannot be parsed (any
    :class:`skills_ref.SkillError`).
    """
    try:
        props = skills_ref.read_properties(skill_md.parent)
    except skills_ref.SkillError:
        return {}
    return props.metadata or {}


def read_source_commit(skill_md: pathlib.Path) -> str | None:
    """Return the 7-char ``source_commit`` recorded in *skill_md*, or ``None``.

    ``None`` is returned when the file is missing or carries no
    ``source_commit`` entry (e.g. the tracked source SKILL.md, which is left
    unstamped -- only built copies carry the commit).
    """
    commit = _read_metadata(skill_md).get("source_commit")
    return commit[:7] if commit else None


def stamp_metadata(
    skill_md: pathlib.Path,
    *,
    version: str | None = None,
    source_commit: str | None = None,
    generated: str | None = None,
) -> None:
    """Record the build-identity ``metadata`` entries in *skill_md*.

    Only the non-``None`` arguments are written, and each is **idempotent**:
    a key already present in the frontmatter ``metadata`` table is left
    untouched. New entries are inserted in :data:`STAMP_KEYS` order under an
    existing ``metadata:`` block (a new block is appended just before the
    closing ``---`` fence when absent). Every other line and the body are
    preserved verbatim. Raises :class:`MissingFrontmatterError` if the file has
    no YAML frontmatter to stamp.
    """
    existing = _read_metadata(skill_md)
    values = {
        "version": version,
        "source_commit": source_commit,
        "generated": generated,
    }
    pending = [
        key
        for key in STAMP_KEYS
        if values[key] is not None and key not in existing
    ]
    if not pending:
        return

    lines = skill_md.read_text(encoding="utf-8").split("\n")
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) < 2:
        raise MissingFrontmatterError(skill_md)
    start, close = fences[0], fences[1]
    front = lines[start + 1 : close]
    entries = [f'  {key}: "{values[key]}"' for key in pending]
    meta_idx = next(
        (i for i, line in enumerate(front) if line.strip() == "metadata:"),
        None,
    )
    if meta_idx is not None:
        front[meta_idx + 1 : meta_idx + 1] = entries
    else:
        front += ["metadata:", *entries]
    lines[start + 1 : close] = front
    skill_md.write_text("\n".join(lines), encoding="utf-8")
