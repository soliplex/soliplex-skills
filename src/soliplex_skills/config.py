"""Load skill specs from a ``[tool.soliplex-skills]`` ``pyproject.toml`` table.

The :class:`~soliplex_skills.versions.SkillSpec` for each skill is recorded in
the source repo's ``pyproject.toml`` so the CLI does not need a wall of flags.
Repos that ship several skills (e.g. ``soliplex-concierge``) list one table per
skill::

    [[tool.soliplex-skills.skill]]
    name = "soliplex-docs"
    owner = "soliplex"
    repo = "soliplex"
    asset_tarball = "soliplex-docs-skill.tar.gz"
    pointer_tag = "docs-latest"
    rolling_prefix = "docs"          # -> the rolling-tag regex

Parsed with the standard-library :mod:`tomllib` -- no third-party dependency.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from soliplex_skills.versions import SkillSpec

_REQUIRED = (
    "name",
    "owner",
    "repo",
    "asset_tarball",
    "pointer_tag",
    "rolling_prefix",
)


class SkillConfigError(ValueError):
    """The ``[tool.soliplex-skills]`` configuration was missing or invalid."""


class PyprojectNotFound(SkillConfigError):
    """No ``pyproject.toml`` was found at or above the search root."""

    def __init__(self, base: Path):
        super().__init__(f"no pyproject.toml found at or above {base}")


class NoSkillEntries(SkillConfigError):
    """A ``pyproject.toml`` had no skill tables."""

    def __init__(self, path: Path):
        super().__init__(
            f"no [[tool.soliplex-skills.skill]] entries in {path}"
        )


class MissingSkillKeys(SkillConfigError):
    """A skill entry omitted one or more required keys."""

    def __init__(self, missing: list[str]):
        keys = ", ".join(missing)
        super().__init__(f"skill entry missing required key(s): {keys}")


class UnknownSkill(SkillConfigError):
    """A requested skill name is not present in the configuration."""

    def __init__(self, name: str, available: list[str]):
        have = ", ".join(available)
        super().__init__(f"no skill {name!r} in config; have: {have}")


class AmbiguousSkill(SkillConfigError):
    """Several skills are configured but none was selected with ``--skill``."""

    def __init__(self, available: list[str]):
        have = ", ".join(available)
        super().__init__(f"several skills configured; pass --skill ({have})")


def find_pyproject(start: Path | None = None) -> Path:
    """Return the nearest ``pyproject.toml`` at/above *start* (cwd default)."""
    base = start or Path.cwd()
    for candidate in [base, *base.parents]:
        path = candidate / "pyproject.toml"
        if path.is_file():
            return path
    raise PyprojectNotFound(base)


def _rolling_re(prefix: str) -> re.Pattern[str]:
    pattern = r"^" + re.escape(prefix) + r"-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"
    return re.compile(pattern)


def _spec_from_entry(entry: dict) -> SkillSpec:
    missing = [key for key in _REQUIRED if key not in entry]
    if missing:
        raise MissingSkillKeys(missing)
    return SkillSpec(
        owner=entry["owner"],
        repo=entry["repo"],
        skill_name=entry["name"],
        asset_tarball=entry["asset_tarball"],
        pointer_tag=entry["pointer_tag"],
        rolling_re=_rolling_re(entry["rolling_prefix"]),
        pointer_manifest=entry.get("pointer_manifest", "latest.json"),
    )


def load_skill_specs(pyproject_path: Path) -> dict[str, SkillSpec]:
    """Return ``{skill_name: SkillSpec}`` from *pyproject_path*.

    Reads the ``[[tool.soliplex-skills.skill]]`` array of tables. Raises
    :class:`SkillConfigError` if the stanza is absent or an entry is invalid.
    """
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    table = data.get("tool", {}).get("soliplex-skills", {})
    entries = table.get("skill", [])
    if not entries:
        raise NoSkillEntries(pyproject_path)
    return {
        spec.skill_name: spec
        for spec in (_spec_from_entry(entry) for entry in entries)
    }
