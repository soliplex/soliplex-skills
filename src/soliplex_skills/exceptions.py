"""Shared exception types for the skill download / install / upgrade flow.

These live here, rather than in the modules that raise them, so the modules can
depend on the exceptions without depending on each other (e.g.
:mod:`soliplex_skills.install` raises :class:`PointerUnavailable`, which
:mod:`soliplex_skills.versions` also raises -- a one-time import cycle). Each
raising module re-exports the names it uses, so existing references such as
``install.SourceInvalid`` or ``versions.PointerUnavailable`` keep working.
"""

from __future__ import annotations

import pathlib


class PointerUnavailable(LookupError):
    """A skill's ``…-latest`` pointer manifest could not be resolved."""

    def __init__(self, pointer_tag: str):
        self.pointer_tag = pointer_tag
        super().__init__(f"could not resolve the {pointer_tag!r} pointer")


class DestinationNotEmpty(ValueError):
    """A download target directory already exists and is not empty."""

    def __init__(self, target: pathlib.Path):
        self.target = target
        super().__init__(f"{target} is not empty; pass force to replace it")


class SourceInvalid(ValueError):
    """An invalid skill was handed to an install / upgrade function."""

    def __init__(self, source_root: pathlib.Path, errors: list[str]):
        self.source_root = source_root
        self.errors = errors
        joined = "\n".join(errors)
        super().__init__(f"{source_root} is not a valid skill:\n{joined}")


class VersionMismatch(ValueError):
    """``install`` found a *different* version already installed.

    Installing would change the version, which is the ``upgrade`` operation's
    job -- so install refuses and raises this instead.
    """

    def __init__(self, skill_root: pathlib.Path):
        self.skill_root = skill_root
        super().__init__(
            f"a different version is already installed at {skill_root}; "
            "use 'upgrade' to replace it"
        )


class NotInstalled(ValueError):
    """``upgrade`` found nothing installed to upgrade.

    Upgrading a skill that is not present would be a de-novo install, which is
    the ``install`` operation's job -- so upgrade refuses and raises this.
    """

    def __init__(self, skill_root: pathlib.Path):
        self.skill_root = skill_root
        super().__init__(
            f"no skill installed at {skill_root}; use 'install' first"
        )
