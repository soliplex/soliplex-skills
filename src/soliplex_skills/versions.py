"""``list`` / ``diff`` / ``upgrade`` for a published filesystem skill.

This consolidates the ~575-line ``skill_versions.py`` that is currently
vendored verbatim into every skill (``soliplex-docs``,
``soliplex-template``, ``soliplex-concierge-{installer,room,admin}``). Those
copies differ only in a handful of constants and one behavioral toggle; both
are captured here by :class:`SkillSpec`, so the vendored script collapses to a
thin shim that builds a ``SkillSpec`` and delegates to :class:`SkillVersions`.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
from pathlib import Path
from typing import Literal

from soliplex_skills import _archive
from soliplex_skills import metadata
from soliplex_skills import releases

#: How ``diff`` compares an installed skill against a published one.
#:
#: * ``"tree"``       -- the whole skill tree (SKILL.md, scripts/, assets/,
#:   references/). Used by ``soliplex-template`` and the concierge skills.
#: * ``"references"`` -- only the ``references/`` Markdown. Used by
#:   ``soliplex-docs``, whose payload is documentation.
CompareScope = Literal["tree", "references"]

_GITHUB = "https://github.com"


class PointerUnavailable(LookupError):
    """A skill's ``…-latest`` pointer manifest could not be resolved."""

    def __init__(self, pointer_tag: str):
        self.pointer_tag = pointer_tag
        super().__init__(f"could not resolve the {pointer_tag!r} pointer")


def _tree_text(root: Path) -> dict[str, list[str]]:
    """Map every file under *root* to its lines (decoded leniently)."""
    out: dict[str, list[str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if _archive.IGNORE_PARTS & set(rel.parts):
            continue
        out[str(rel).replace("\\", "/")] = path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
    return out


def _markdown(refs_dir: Path) -> dict[str, list[str]]:
    """Map every ``*.md`` file under *refs_dir* to its lines."""
    out: dict[str, list[str]] = {}
    if not refs_dir.is_dir():
        return out
    for path in sorted(refs_dir.rglob("*.md")):
        rel = str(path.relative_to(refs_dir)).replace("\\", "/")
        out[rel] = path.read_text(encoding="utf-8").splitlines()
    return out


def _diff_trees(
    left: dict[str, list[str]],
    right: dict[str, list[str]],
    *,
    left_label: str,
    right_label: str,
    name_only: bool,
) -> int:
    """Print the difference between two file→lines maps; return 0/1."""
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    common = sorted(set(left) & set(right))
    changed = [name for name in common if left[name] != right[name]]

    if not (added or removed or changed):
        print("No differences.")
        return 0

    for name in removed:
        print(f"- removed: {name}")
    for name in added:
        print(f"+ added:   {name}")
    for name in changed:
        print(f"~ changed: {name}")

    if name_only:
        return 1

    print()
    for name in changed:
        diff = difflib.unified_diff(
            left[name],
            right[name],
            fromfile=f"{left_label}/{name}",
            tofile=f"{right_label}/{name}",
            lineterm="",
        )
        print("\n".join(diff))
        print()
    return 1


@dataclasses.dataclass(frozen=True)
class SkillSpec:
    """Everything that distinguishes one published skill from another.

    These are exactly the constants that differ between the vendored
    ``skill_versions.py`` copies today.

    Attributes:
        owner: GitHub repository owner (e.g. ``"soliplex"``).
        repo: GitHub repository name the skill is released from.
        skill_name: The skill's directory / SKILL.md name.
        asset_tarball: Release asset filename (e.g.
            ``"soliplex-docs-skill.tar.gz"``).
        pointer_tag: The ``…-latest`` tag carrying ``latest.json`` (e.g.
            ``"docs-latest"``).
        rolling_re: Pattern identifying rolling-build tags (e.g.
            ``^docs-\\d{4}\\.\\d{2}\\.\\d{2}-[0-9a-f]+$``). Tags that do not
            match are treated as tagged releases -- whether they live on the
            repo's own ``v…`` tag (a repo-coupled skill) or under the skill's
            own ``<skill>-vX.Y.Z`` namespace (an independently-versioned
            skill) is irrelevant to the client; both are just "release" tags
            carrying this skill's :attr:`asset_tarball`.
        compare_scope: See :data:`CompareScope`.
        pointer_manifest: Manifest filename under the pointer tag.
    """

    owner: str
    repo: str
    skill_name: str
    asset_tarball: str
    pointer_tag: str
    rolling_re: re.Pattern[str]
    compare_scope: CompareScope = "tree"
    pointer_manifest: str = "latest.json"


class SkillVersions:
    """Operations over a published skill's GitHub releases.

    Wraps a :class:`SkillSpec` and offers the three subcommands the vendored
    script exposes. ``target`` arguments accept a concrete tag or the literal
    ``"latest"``, which is expanded via the skill's pointer manifest.
    """

    def __init__(self, spec: SkillSpec):
        self.spec = spec

    # -- URL construction ---------------------------------------------------

    def _download_base(self) -> str:
        spec = self.spec
        return f"{_GITHUB}/{spec.owner}/{spec.repo}/releases/download"

    def _asset_url(self, tag: str) -> str:
        return f"{self._download_base()}/{tag}/{self.spec.asset_tarball}"

    def _pointer_url(self) -> str:
        return (
            f"{self._download_base()}/{self.spec.pointer_tag}"
            f"/{self.spec.pointer_manifest}"
        )

    # -- target resolution & fetching --------------------------------------

    def _resolve_target(self, target: str) -> tuple[str, str, str | None]:
        """Resolve *target* to ``(tag, asset_url, sha256)``.

        ``"latest"`` is expanded via the skill's pointer manifest (verified
        sha256); an explicit tag builds the asset URL by name (no sha256).
        """
        if target == "latest":
            pointer = releases.read_pointer(self._pointer_url())
            if pointer is None:
                raise PointerUnavailable(self.spec.pointer_tag)
            return pointer.tag, pointer.asset_url, pointer.sha256
        return target, self._asset_url(target), None

    def _fetch_skill_root(
        self, asset_url: str, sha256: str | None, dest: Path
    ) -> Path:
        extract_dir = _archive.download_and_extract(
            asset_url, dest, expected_sha256=sha256
        )
        return _archive.find_skill_root(extract_dir)

    def _read_for_scope(self, skill_root: Path) -> dict[str, list[str]]:
        if self.spec.compare_scope == "references":
            return _markdown(skill_root / "references")
        return _tree_text(skill_root)

    # -- public API ---------------------------------------------------------

    def list(
        self, *, kind: Literal["rolling", "release"] | None = None
    ) -> list[dict]:
        """Return skill-bearing releases, newest first (minus the pointer).

        Each entry carries ``tag``, ``date``, ``kind``, ``commit`` and
        ``prerelease``. *kind* optionally filters to rolling builds or tagged
        releases.
        """
        out: list[dict] = []
        for release in releases.list_releases(self.spec.owner, self.spec.repo):
            tag = release.get("tag_name")
            if tag == self.spec.pointer_tag:
                continue
            if not releases.has_asset(release, self.spec.asset_tarball):
                continue
            release_kind, commit = releases.classify(
                release, rolling_re=self.spec.rolling_re
            )
            out.append(
                {
                    "tag": tag,
                    "date": (release.get("published_at") or "")[:10],
                    "kind": release_kind,
                    "commit": commit,
                    "prerelease": release.get("prerelease", False),
                }
            )
        out.sort(key=lambda item: item["date"], reverse=True)
        if kind:
            out = [item for item in out if item["kind"] == kind]
        return out

    def diff(
        self,
        installed_path: Path,
        target: str = "latest",
        *,
        name_only: bool = False,
    ) -> int:
        """Show how the skill at *installed_path* differs from *target*.

        Honors :attr:`SkillSpec.compare_scope`. Returns ``0`` when identical,
        ``1`` when differences were reported (a process-style status code).
        """
        with _archive.temp_dest() as dest:
            tag, asset_url, sha256 = self._resolve_target(target)
            published_root = self._fetch_skill_root(asset_url, sha256, dest)
            return _diff_trees(
                self._read_for_scope(installed_path),
                self._read_for_scope(published_root),
                left_label="installed",
                right_label=tag,
                name_only=name_only,
            )

    def upgrade(
        self,
        installed_path: Path,
        target: str = "latest",
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> int:
        """Download *target* and install it over *installed_path*.

        The tarball's sha256 is verified against the manifest when known, and
        files are replaced in place -- directories removed first -- so files
        deleted upstream do not linger. A no-op when the installed
        ``source_commit`` already matches *target* unless *force* is set;
        *dry_run* reports the plan without writing. Returns a status code.
        """
        installed = metadata.read_source_commit(installed_path / "SKILL.md")
        with _archive.temp_dest() as dest:
            tag, asset_url, sha256 = self._resolve_target(target)
            new_root = self._fetch_skill_root(asset_url, sha256, dest)
            new_commit = metadata.read_source_commit(new_root / "SKILL.md")

            if new_commit and new_commit == installed and not force:
                print(
                    f"Already up to date: installed commit {installed} "
                    f"matches {tag}. Use force=True to reinstall."
                )
                return 0

            summary = (
                f"{tag} (commit {new_commit or 'unknown'}; "
                f"installed {installed or 'unknown'})"
            )
            if dry_run:
                print(f"Would upgrade to {summary}.")
                return 0

            _archive.install_over(new_root, installed_path)

        print(f"Upgraded {self.spec.skill_name} to {summary}.")
        return 0
