"""Shared fixtures and helpers for the unit suite.

Everything here keeps the suite **offline**: skills, tarballs, and release
manifests are synthesized on disk and addressed via ``file://`` URLs, and the
single network seam (``soliplex_skills.releases.fetch``) is monkeypatched where
the GitHub releases *API* is involved. No test touches the network.
"""

from __future__ import annotations

from collections import abc
from pathlib import Path

import pytest


def render_skill_md(
    frontmatter_lines: abc.Sequence[str], *, body: str = "# Demo skill\n"
) -> str:
    """Return SKILL.md text wrapping *frontmatter_lines* in ``---`` fences."""
    front = "\n".join(frontmatter_lines)
    return f"---\n{front}\n---\n\n{body}"


@pytest.fixture
def write_skill_md(tmp_path: Path):
    """Write a SKILL.md from frontmatter lines; return its path."""

    def _write(
        frontmatter_lines: abc.Sequence[str],
        *,
        body: str = "# Demo skill\n",
        dest: Path | None = None,
    ) -> Path:
        path = dest or (tmp_path / "SKILL.md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            render_skill_md(frontmatter_lines, body=body), encoding="utf-8"
        )
        return path

    return _write
