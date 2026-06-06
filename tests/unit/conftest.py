"""Shared fixtures and helpers for the unit suite.

Everything here keeps the suite **offline**: skills, tarballs, and release
manifests are synthesized on disk and addressed via ``file://`` URLs, and the
single network seam (``soliplex_skills.releases.fetch``) is monkeypatched where
the GitHub releases *API* is involved. No test touches the network.
"""

from __future__ import annotations

import tarfile
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


@pytest.fixture
def make_skill(tmp_path: Path):
    """Build a skill tree (SKILL.md + given files); return its root dir."""

    def _make(
        name: str = "demo-skill",
        *,
        commit: str | None = "abc1234",
        files: abc.Mapping[str, str] | None = None,
        parent: Path | None = None,
    ) -> Path:
        root = (parent or tmp_path) / name
        root.mkdir(parents=True, exist_ok=True)
        front = [f"name: {name}"]
        if commit is not None:
            front += ["metadata:", f'  source_commit: "{commit}"']
        (root / "SKILL.md").write_text(
            render_skill_md(front), encoding="utf-8"
        )
        for rel, content in (files or {}).items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        return root

    return _make


@pytest.fixture
def make_tarball():
    """Pack a skill dir into ``<name>/...`` inside a ``.tar.gz``; return it."""

    def _make(skill_dir: Path, dest_tar: Path) -> Path:
        with tarfile.open(dest_tar, "w:gz") as archive:
            archive.add(skill_dir, arcname=skill_dir.name)
        return dest_tar

    return _make
