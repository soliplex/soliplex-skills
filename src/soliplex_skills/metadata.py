"""Read and stamp a skill's installed identity in ``SKILL.md`` frontmatter.

A built skill records the commit it was assembled from as
``metadata.source_commit`` in its ``SKILL.md`` YAML frontmatter.

That value is the skill's installed identity: the build step stamps it
(:func:`stamp_source_commit`) and ``versions``/``releases`` read it back
(:func:`read_source_commit`) to tell which published build is installed.
"""

from __future__ import annotations

import re
from pathlib import Path

#: Matches a ``source_commit: "abc1234"`` frontmatter line (quotes optional).
COMMIT_RE = re.compile(r'^\s*source_commit:\s*"?([0-9a-fA-F]+)"?\s*$')


class MissingFrontmatterError(ValueError):
    """A ``SKILL.md`` had no YAML frontmatter to stamp."""

    def __init__(self, skill_md: Path):
        super().__init__(f"{skill_md} has no YAML frontmatter to stamp")


def read_source_commit(skill_md: Path) -> str | None:
    """Return the 7-char ``source_commit`` recorded in *skill_md*, or ``None``.

    ``None`` is returned when the file is missing or carries no
    ``source_commit`` entry (e.g. the tracked source SKILL.md, which is left
    unstamped -- only built copies carry the commit).
    """
    if not skill_md.exists():
        return None
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        match = COMMIT_RE.match(line)
        if match:
            return match.group(1)[:7]
    return None


def stamp_source_commit(skill_md: Path, commit: str) -> None:
    """Record ``metadata.source_commit: "<commit>"`` in *skill_md*.

    Idempotent: a SKILL.md that already carries a ``source_commit`` is left
    untouched. The entry is inserted under an existing ``metadata:`` block if
    present, otherwise a new ``metadata:`` block is appended just before the
    closing ``---`` fence. Raises if the file has no YAML frontmatter to stamp.
    """
    lines = skill_md.read_text(encoding="utf-8").split("\n")
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) < 2:
        raise MissingFrontmatterError(skill_md)
    start, close = fences[0], fences[1]
    front = lines[start + 1 : close]
    if any(line.strip().startswith("source_commit:") for line in front):
        return  # already stamped
    entry = f'  source_commit: "{commit}"'
    meta_idx = next(
        (i for i, line in enumerate(front) if line.strip() == "metadata:"),
        None,
    )
    if meta_idx is not None:
        front.insert(meta_idx + 1, entry)
    else:
        front += ["metadata:", entry]
    lines[start + 1 : close] = front
    skill_md.write_text("\n".join(lines), encoding="utf-8")
