"""Assemble, stamp, and validate a skill into a distribution directory.

This is the build half of the release pipeline, generalizing the per-repo
``build_skill.py`` / ``build_skills.py`` / ``generate_docs_skill.py`` scripts:
copy a skill's source tree into ``dist/<name>/``, stamp its ``SKILL.md`` with
the source commit, and validate it with the agent-skills reference tool. The
CI workflow then packages ``dist/<name>/`` into release assets.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from soliplex_skills import metadata


class SkillNotFound(ValueError):
    """No skill directory (with a ``SKILL.md``) was found at the path."""

    def __init__(self, name: str, skills_dir: Path):
        super().__init__(f"no skill named {name!r} under {skills_dir}")


class ValidatorUnavailable(RuntimeError):
    """Neither ``agentskills`` nor ``uvx`` is available to validate a skill."""

    def __init__(self) -> None:
        super().__init__(
            "cannot find the agent-skills validator; install 'skills-ref' "
            "or run under 'uv'/'uvx'"
        )


class ValidationFailed(RuntimeError):
    """The agent-skills validator rejected a built skill."""

    def __init__(self, name: str):
        super().__init__(f"skill validation failed for {name!r}")


def discover_skills(skills_dir: Path) -> list[str]:
    """Return the names of every skill directory under *skills_dir*.

    A skill directory is one containing a ``SKILL.md``. Useful for repos that
    ship several skills (e.g. ``soliplex-concierge``).
    """
    return sorted(
        path.name
        for path in skills_dir.iterdir()
        if (path / "SKILL.md").is_file()
    )


def git_head_commit(repo_dir: Path) -> str | None:
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


def validator_cmd() -> list[str]:
    """Resolve how to invoke the agent-skills validator.

    Prefer the ``agentskills`` executable on PATH; otherwise fall back to
    ``uvx --from skills-ref agentskills``. Raises :class:`ValidatorUnavailable`
    when neither is present.
    """
    exe = shutil.which("agentskills")
    if exe:
        return [exe, "validate"]
    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "--from", "skills-ref", "agentskills", "validate"]
    raise ValidatorUnavailable


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
    source tree's git HEAD when ``None``), and -- when *validate* -- runs the
    agent-skills validator. Returns the built ``dist/<name>/`` path.
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

    if validate:
        result = subprocess.run([*validator_cmd(), str(out)], check=False)
        if result.returncode != 0:
            raise ValidationFailed(name)

    return out
