"""Download, install, and defang a published skill.

Where :mod:`soliplex_skills.versions` manages a skill that is *already*
installed (upgrading it in place), this module covers the first-time install:

- resolve a published skill to an asset
- download and verify it
- extract its skill root
- optionally strip the self-management helper and its documentation, so the
  copy is safe to run inside a Soliplex room agent.
"""

from __future__ import annotations

import dataclasses
import enum
import pathlib
import re
import shutil

import skills_ref

from soliplex_skills import _archive
from soliplex_skills import metadata
from soliplex_skills import releases
from soliplex_skills.versions import PointerUnavailable

_GITHUB = "https://github.com"

#: Default note replacing the self-management section in a defanged skill.
#: Use :func:`format_defang_note` to render it with the installer name.
_DEFANG_NOTE = """\
{heading}

This copy was installed into the Soliplex stack by the `{installed_by}` skill
and runs inside a room agent, not a coding agent. Its
`scripts/skill_versions.py` self-management helper has been removed: do **not**
try to list, diff, or upgrade this skill from inside the room.
"""


def format_defang_note(heading: str, *, installed_by: str) -> str:
    """Return the default defang note for *heading* and *installed_by*."""
    return _DEFANG_NOTE.format(heading=heading, installed_by=installed_by)


#: Markers identifying ``compatibility`` frontmatter verbiage about the removed
#: self-management helper. A ``compatibility`` sentence naming any of these
#: (the bundled helper or the library behind it) describes a requirement the
#: defanged copy no longer has, so it is dropped. Body prose is matched
#: separately, by section -- see :func:`defang_skill`.
_HELPER_MARKERS = ("skill_versions.py", "soliplex-skills")


def _scrub_compatibility(lines: list[str]) -> None:
    """Drop helper-requirement sentences from ``compatibility`` frontmatter.

    Operates in place on *lines* (``splitlines(keepends=True)`` form). Within
    the leading YAML frontmatter, the single-line ``compatibility:`` value (if
    any) is split into sentences and those naming a :data:`_HELPER_MARKERS`
    token are removed; the whole line is dropped if nothing else remains. A
    file with no frontmatter, no ``compatibility`` line, or no matching
    sentence is left byte-for-byte unchanged.
    """
    fences = [i for i, line in enumerate(lines) if line.strip() == "---"]
    if len(fences) < 2:
        return
    idx = next(
        (
            i
            for i in range(fences[0] + 1, fences[1])
            if lines[i].lstrip().startswith("compatibility:")
        ),
        None,
    )
    if idx is None:
        return

    raw = lines[idx]
    newline = "\n" if raw.endswith("\n") else ""
    indent = raw[: len(raw) - len(raw.lstrip())]
    after = raw.strip()[len("compatibility:") :].strip()
    quote = ""
    if len(after) >= 2 and after[0] in "\"'" and after[-1] == after[0]:
        quote, after = after[0], after[1:-1]

    sentences = re.split(r"(?<=\.)\s+", after)
    kept = [
        s
        for s in sentences
        if not any(marker in s for marker in _HELPER_MARKERS)
    ]
    if kept == sentences:  # nothing helper-related; leave it untouched
        return
    value = " ".join(kept).strip()
    if value:
        lines[idx] = f"{indent}compatibility: {quote}{value}{quote}{newline}"
    else:
        del lines[idx]


@dataclasses.dataclass(frozen=True)
class PublishedSkill:
    """A filesystem skill published as a GitHub-release tarball.

    Attributes:
        name: The skill's SKILL.md / directory name.
        owner: GitHub repository owner.
        repo: GitHub repository name.
        asset_tarball: Release asset filename.
        pointer_tag: The ``…-latest`` tag carrying the pointer manifest.
        pointer_manifest: Manifest filename under the pointer tag.
    """

    name: str
    owner: str
    repo: str
    asset_tarball: str
    pointer_tag: str
    pointer_manifest: str = "latest.json"

    @property
    def download_base(self) -> str:
        """Base URL for this repo's release-download assets."""
        return f"{_GITHUB}/{self.owner}/{self.repo}/releases/download"

    def asset_url(self, tag: str) -> str:
        """Direct download URL for this skill's asset under *tag*."""
        return f"{self.download_base}/{tag}/{self.asset_tarball}"

    def pointer_url(self) -> str:
        """URL of the ``…-latest`` pointer manifest."""
        return (
            f"{self.download_base}/{self.pointer_tag}/{self.pointer_manifest}"
        )


class DestinationNotEmpty(ValueError):
    """A download target directory already exists and is not empty."""

    def __init__(self, target: pathlib.Path):
        self.target = target
        super().__init__(f"{target} is not empty; pass force to replace it")


def download_skill(
    spec: PublishedSkill,
    version: str | None,
    dest: pathlib.Path,
    *,
    force: bool = False,
) -> pathlib.Path:
    """Download *spec* and place its skill tree at ``<dest>/<name>/``.

    When *version* is ``None`` the skill's ``latest`` pointer is read (and its
    recorded sha256 verified); an explicit tag builds the asset URL by name.
    The asset is extracted in a scratch directory and the skill root copied to
    ``<dest>/<spec.name>/`` (the returned path).

    A **non-empty** target directory is left untouched and
    :class:`DestinationNotEmpty` is raised unless *force* is true; an empty or
    absent target is replaced / created. The check happens before any network
    access, so a refused download touches neither the network nor *dest*.
    """
    target = dest / spec.name
    if target.is_dir() and any(target.iterdir()) and not force:
        raise DestinationNotEmpty(target)

    if version is None:
        pointer = releases.read_pointer(spec.pointer_url())
        if pointer is None:
            raise PointerUnavailable(spec.pointer_tag)
        asset_url, sha256 = pointer.asset_url, pointer.sha256
    else:
        asset_url, sha256 = spec.asset_url(version), None

    with _archive.temp_dest() as scratch:
        extract_dir = _archive.download_and_extract(
            asset_url, scratch, expected_sha256=sha256
        )
        root = _archive.find_skill_root(extract_dir)
        if target.exists():
            shutil.rmtree(target)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root, target)
    return target


def defang_skill(
    skill_dir: pathlib.Path,
    *,
    installed_by: str,
    note: str | None = None,
) -> None:
    """Strip the self-management helper from a stack-installed skill.

    Removes ``scripts/skill_versions.py`` and any ``scripts/__pycache__``,
    then removes ``scripts/`` if it is empty. Rewrites the ``SKILL.md``
    section that references ``skill_versions.py`` (located by scanning
    ``## `` headings and checking which section body contains the helper
    name) to a short note explaining that updates must be driven from the
    outside via *installed_by*. Callers may pass a custom *note*; use
    :func:`format_defang_note` to build the default note. Any
    ``compatibility`` frontmatter sentence describing the now-removed helper's
    requirements (the bundled script, the ``soliplex-skills`` library, the
    network/GitHub access it needs) is dropped too -- see
    :func:`_scrub_compatibility`.

    If no ``SKILL.md`` section mentions the helper, only the script file(s)
    are removed and the markdown is left untouched.
    """
    helper = skill_dir / "scripts" / "skill_versions.py"
    helper.unlink(missing_ok=True)
    pycache = skill_dir / "scripts" / "__pycache__"
    if pycache.is_dir():
        shutil.rmtree(pycache)
    scripts = skill_dir / "scripts"
    if scripts.is_dir() and not any(scripts.iterdir()):
        scripts.rmdir()

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return
    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    _scrub_compatibility(lines)
    heads = [i for i, line in enumerate(lines) if line.startswith("## ")]
    for n, start in enumerate(heads):
        end = heads[n + 1] if n + 1 < len(heads) else len(lines)
        if "skill_versions.py" not in "".join(lines[start:end]):
            continue
        heading = lines[start].rstrip("\n")
        block = note or format_defang_note(heading, installed_by=installed_by)
        if end < len(lines):  # keep a blank line before the next section
            block += "\n"
        lines[start:end] = [block]
        break
    skill_md.write_text("".join(lines), encoding="utf-8")


class InstallStatus(enum.StrEnum):
    """Statuses returned by :func:`install_skill`."""

    ADDED = "added"
    UNCHANGED = "unchanged"
    UPGRADED = "upgraded"


class SourceInvalid(ValueError):
    """An invalid skill was handed to :func:`install_skill_from`."""

    def __init__(self, source_root: pathlib.Path, errors: list[str]):
        self.source_root = source_root
        self.errors = errors
        joined = "\n".join(errors)
        super().__init__(f"{source_root} is not a valid skill:\n{joined}")


def install_skill_from(
    source_root: pathlib.Path,
    dest: pathlib.Path,
    *,
    installed_by: str,
    defang: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[pathlib.Path, InstallStatus]:
    """Install an already-extracted *source_root* skill tree under *dest*.

    *source_root* is a directory containing ``SKILL.md`` (a published tarball
    extracted by :func:`download_skill`, or a local working copy). It is
    **validated** against the agent-skills spec first
    (:class:`SourceInvalid` on failure) and installed over
    ``<dest>/<name>/``, where *name* is the skill's own ``name`` -- the
    validator guarantees it equals the source directory's name, so the install
    cannot produce a spec-invalid directory. Use this directly to install from
    a local directory (offline / development), or via :func:`install_skill` for
    a published one.

    Returns ``(skill_root, status)`` as :func:`install_skill` does. When the
    target exists and its ``metadata.source_commit`` already matches the
    source's, the skill is returned :attr:`~InstallStatus.UNCHANGED` unless
    *force* is true. *dry_run* reports the plan without writing anything.

    *source_root* is never modified: when *defang* is true (the default), the
    self-management helper is stripped from the installed *copy*, so a local
    source directory is left byte-for-byte intact.
    """
    errors = skills_ref.validate(source_root)
    if errors:
        raise SourceInvalid(source_root, errors)

    skill_root = dest / source_root.name
    installed_commit = None
    if skill_root.exists():
        installed_commit = metadata.read_source_commit(skill_root / "SKILL.md")
    source_commit = metadata.read_source_commit(source_root / "SKILL.md")

    if (
        skill_root.exists()
        and source_commit
        and source_commit == installed_commit
        and not force
    ):
        return skill_root, InstallStatus.UNCHANGED

    upgrading = skill_root.exists()
    status = InstallStatus.UPGRADED if upgrading else InstallStatus.ADDED
    if dry_run:
        return skill_root, status

    if upgrading:
        _archive.install_over(source_root, skill_root)
    else:
        shutil.copytree(source_root, skill_root)
    if defang:
        defang_skill(skill_root, installed_by=installed_by)
    return skill_root, status


def _resolve_target_commit(
    spec: PublishedSkill, version: str | None
) -> str | None:
    """The published target's ``source_commit`` without downloading the asset.

    Reads it from the ``latest`` pointer manifest (a small JSON) when *version*
    is ``None``; an explicit tag carries no such pointer, so the commit is
    unknowable without pulling the asset and ``None`` is returned.
    """
    if version is not None:
        return None
    pointer = releases.read_pointer(spec.pointer_url())
    if pointer is None:
        raise PointerUnavailable(spec.pointer_tag)
    return pointer.source_commit


def install_skill(
    spec: PublishedSkill,
    version: str | None,
    dest: pathlib.Path,
    *,
    installed_by: str,
    defang: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[pathlib.Path, InstallStatus]:
    """Download *spec* and install it under *dest*.

    The skill is downloaded + extracted into a temporary directory, then
    installed over ``<dest>/<skill-name>/`` via
    :func:`install_skill_from` (which defangs the installed copy when
    *defang* is true).

    Returns ``(skill_root, status)`` where *status* is one of
    :attr:`InstallStatus.ADDED`, :attr:`InstallStatus.UNCHANGED`, or
    :attr:`InstallStatus.UPGRADED`. An existing skill whose
    ``metadata.source_commit`` already matches the published target is
    returned unchanged unless *force* is true.

    *dry_run* reports the plan **without downloading the asset**: it resolves
    the target commit from the ``latest`` pointer (so the status is exact),
    but an explicit tag carries no pointer, so a present skill is reported
    :attr:`~InstallStatus.UPGRADED` (``UNCHANGED`` can't be proven without the
    asset). For a fully offline, exact dry-run, use
    :func:`install_skill_from` with ``dry_run=True``.
    """
    skill_root = dest / spec.name
    if dry_run:
        installed_commit = None
        if skill_root.exists():
            installed_commit = metadata.read_source_commit(
                skill_root / "SKILL.md"
            )
        target_commit = _resolve_target_commit(spec, version)
        if (
            skill_root.exists()
            and target_commit
            and target_commit == installed_commit
            and not force
        ):
            return skill_root, InstallStatus.UNCHANGED
        if skill_root.exists():
            return skill_root, InstallStatus.UPGRADED
        return skill_root, InstallStatus.ADDED

    with _archive.temp_dest() as tmp:
        new_root = download_skill(spec, version, tmp)
        return install_skill_from(
            new_root,
            dest,
            installed_by=installed_by,
            defang=defang,
            force=force,
        )
