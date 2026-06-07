"""Assemble, stamp, and validate a skill into a distribution directory.

This is the build half of the release pipeline, generalizing the per-repo
``build_skill.py`` / ``build_skills.py`` / ``generate_docs_skill.py`` scripts:
copy a skill's source tree into ``dist/<name>/``, stamp its ``SKILL.md`` with
the source commit, and validate it with the agent-skills reference library.

The CI workflow then packages ``dist/<name>/`` into release assets.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
from collections import abc as collections_abc

import skills_ref

from soliplex_skills import metadata

SkillGenerator = collections_abc.Callable[[pathlib.Path], None]


class SkillNotFound(ValueError):
    """No skill directory (with a ``SKILL.md``) was found at the path."""

    def __init__(self, name: str, skills_dir: pathlib.Path):
        super().__init__(f"no skill named {name!r} under {skills_dir}")


class ValidationFailed(RuntimeError):
    """The agent-skills validator rejected a built skill."""

    def __init__(self, name: str, errors: list[str]):
        self.name = name
        self.errors = errors
        super().__init__(
            f"skill validation failed for {name!r}:\n{'\n'.join(errors)}"
        )


def discover_skills(skills_dir: pathlib.Path) -> list[str]:
    """Return the names of every skill directory under *skills_dir*.

    A skill directory is one containing a ``SKILL.md``. Useful for repos that
    ship several skills (e.g. ``soliplex-concierge``).
    """
    return sorted(
        path.name
        for path in skills_dir.iterdir()
        if (path / "SKILL.md").is_file()
    )


def git_head_commit(repo_dir: pathlib.Path) -> str | None:
    """Return *repo_dir*'s current commit SHA, or ``None`` if unavailable."""
    if shutil.which("git") is None:
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    return result.stdout.strip() or None


def build_skill(
    name: str,
    *,
    src: pathlib.Path,
    dist: pathlib.Path,
    commit: str | None = None,
    validate: bool = True,
    generator: SkillGenerator | None = None,
) -> pathlib.Path:
    """Assemble, stamp, and validate skill *name* into ``dist/<name>/``.

    Copies ``src/<name>/`` to ``dist/<name>/`` (skipping ``__pycache__``) and
    stamps ``SKILL.md`` with *commit* via
    :func:`soliplex_skills.metadata.stamp_source_commit` (defaulting to the
    source tree's git HEAD when ``None``). If *generator* is given, it is then
    called with the built ``dist/<name>/`` path -- a hook for build-time
    content, e.g. the docs skill copies ``docs/`` into ``references/`` and
    appends a nav-derived map to ``SKILL.md``. Finally, when *validate*, the
    agent-skills validator is run. Returns the built ``dist/<name>/`` path.
    """
    source = src / name
    if not (source / "SKILL.md").is_file():
        raise SkillNotFound(name, src)

    out = dist / name
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(source, out, ignore=shutil.ignore_patterns("__pycache__"))

    resolved = commit if commit is not None else git_head_commit(source)
    if resolved:
        metadata.stamp_source_commit(out / "SKILL.md", resolved)

    if generator is not None:
        generator(out)

    if validate:
        errors = skills_ref.validate(out)
        if errors:
            raise ValidationFailed(name, errors)

    return out
