"""``list`` / ``diff`` / ``upgrade`` for a published filesystem skill.

Each skill bundles a thin ``skill_versions.py`` shim that builds a
:class:`SkillSpec` -- the handful of constants that distinguish one skill from
another -- and delegates to :class:`SkillVersions`, which implements the three
subcommands here.
"""

from __future__ import annotations

import dataclasses
import difflib
import pathlib
import re
import typing
import warnings

from soliplex_skills import _archive
from soliplex_skills import metadata
from soliplex_skills import releases

_GITHUB = "https://github.com"


class PointerUnavailable(LookupError):
    """A skill's ``…-latest`` pointer manifest could not be resolved."""

    def __init__(self, pointer_tag: str):
        self.pointer_tag = pointer_tag
        super().__init__(f"could not resolve the {pointer_tag!r} pointer")


def _tree_text(root: pathlib.Path) -> dict[str, list[str]]:
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


def _read_tree(root: pathlib.Path) -> dict[str, list[str]]:
    """Map every file under *root* to its lines, normalizing the build stamp.

    The per-build ``metadata.source_commit`` line stamped into ``SKILL.md`` is
    dropped so two builds of identical content compare equal; every other line
    (including the build-time ``## Documentation map``) is kept.
    """
    files = _tree_text(root)
    for rel, lines in files.items():
        if rel == "SKILL.md":
            files[rel] = [
                line for line in lines if not metadata.COMMIT_RE.match(line)
            ]
    return files


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

    A skill's bundled ``skill_versions.py`` shim fills these in.

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
        pointer_manifest: Manifest filename under the pointer tag.

    .. deprecated::
        ``compare_scope`` is accepted for backward compatibility but ignored:
        ``diff`` always compares the whole skill tree (the per-build
        ``source_commit`` stamp is normalized out). Passing it warns.
    """

    owner: str
    repo: str
    skill_name: str
    asset_tarball: str
    pointer_tag: str
    rolling_re: re.Pattern[str]
    pointer_manifest: str = "latest.json"
    compare_scope: dataclasses.InitVar[str | None] = None

    def __post_init__(self, compare_scope: str | None) -> None:
        if compare_scope is not None:
            warnings.warn(
                "SkillSpec.compare_scope is deprecated and ignored; diff "
                "compares the whole skill tree (the source_commit stamp is "
                "normalized out).",
                DeprecationWarning,
                stacklevel=2,
            )


class SkillVersions:
    """Operations over a published skill's GitHub releases.

    Wraps a :class:`SkillSpec` and offers the three subcommands the bundled
    shim exposes. ``target`` arguments accept a concrete tag or the literal
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
        self, asset_url: str, sha256: str | None, dest: pathlib.Path
    ) -> pathlib.Path:
        extract_dir = _archive.download_and_extract(
            asset_url, dest, expected_sha256=sha256
        )
        return _archive.find_skill_root(extract_dir)

    # -- public API ---------------------------------------------------------

    def list(
        self,
        *,
        kind: typing.Literal["rolling", "release"] | None = None,
        installed_path: pathlib.Path | None = None,
        mark_latest: bool = False,
    ) -> list[dict]:
        """Return skill-bearing releases, newest first (minus the pointer).

        Each entry carries ``tag``, ``date``, ``kind``, ``commit``,
        ``prerelease`` and the ``installed`` / ``latest`` flags. *kind*
        optionally filters to rolling builds or tagged releases. When
        *installed_path* is given, the row whose commit matches that skill's
        recorded ``source_commit`` is flagged ``installed``; when *mark_latest*
        is set, the row the ``…-latest`` pointer resolves to is flagged
        ``latest`` (silently left unflagged if the pointer is unavailable).
        """
        installed_commit = (
            metadata.read_source_commit(installed_path / "SKILL.md")
            if installed_path is not None
            else None
        )
        latest_tag: str | None = None
        if mark_latest:
            try:
                latest_tag = self._resolve_target("latest")[0]
            except PointerUnavailable:
                latest_tag = None

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
                    "installed": installed_commit is not None
                    and commit == installed_commit,
                    "latest": latest_tag is not None and tag == latest_tag,
                }
            )
        out.sort(key=lambda item: item["date"], reverse=True)
        if kind:
            out = [item for item in out if item["kind"] == kind]
        return out

    def diff(
        self,
        installed_path: pathlib.Path,
        target: str = "latest",
        *,
        name_only: bool = False,
    ) -> int:
        """Show how the skill at *installed_path* differs from *target*.

        Compares the whole skill tree; the per-build ``source_commit`` stamp in
        ``SKILL.md`` is ignored. Returns ``0`` when identical, ``1`` when
        differences were reported (a process-style status code).
        """
        with _archive.temp_dest() as dest:
            tag, asset_url, sha256 = self._resolve_target(target)
            published_root = self._fetch_skill_root(asset_url, sha256, dest)
            return _diff_trees(
                _read_tree(installed_path),
                _read_tree(published_root),
                left_label="installed",
                right_label=tag,
                name_only=name_only,
            )

    def diff_published(
        self,
        left: str,
        right: str,
        *,
        name_only: bool = False,
    ) -> int:
        """Show how two *published* versions differ from each other.

        Neither side need be installed: *left* and *right* are each a concrete
        tag or the literal ``"latest"`` (expanded via the pointer manifest).
        Compares the whole skill tree; the per-build ``source_commit`` stamp in
        ``SKILL.md`` is ignored. Returns ``0`` when identical, ``1`` when
        differences were reported.
        """
        with (
            _archive.temp_dest() as dest_left,
            _archive.temp_dest() as dest_right,
        ):
            left_tag, left_url, left_sha = self._resolve_target(left)
            right_tag, right_url, right_sha = self._resolve_target(right)
            left_root = self._fetch_skill_root(left_url, left_sha, dest_left)
            right_root = self._fetch_skill_root(
                right_url, right_sha, dest_right
            )
            return _diff_trees(
                _read_tree(left_root),
                _read_tree(right_root),
                left_label=left_tag,
                right_label=right_tag,
                name_only=name_only,
            )

    def upgrade(
        self,
        installed_path: pathlib.Path,
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


def format_list_table(rows: list[dict]) -> str:
    """Render :meth:`SkillVersions.list` *rows* as an aligned table.

    Produces a ``TAG  DATE  KIND  COMMIT`` header and one row per version,
    appending ``← installed, latest`` for rows carrying the ``installed`` /
    ``latest`` flags. The tag column is sized to the widest tag. Returns the
    'no versions' message when *rows* is empty. The library CLI and the
    per-skill shim both render through this, so their output stays identical.
    """
    if not rows:
        return "No published versions found."
    tag_width = max(len("TAG"), *(len(row["tag"]) for row in rows))
    lines = [f"{'TAG':<{tag_width}}  {'DATE':<10}  {'KIND':<7}  COMMIT"]
    for row in rows:
        marks = []
        if row.get("installed"):
            marks.append("installed")
        if row.get("latest"):
            marks.append("latest")
        suffix = f"  ← {', '.join(marks)}" if marks else ""
        lines.append(
            f"{row['tag']:<{tag_width}}  "
            f"{row['date']:<10}  "
            f"{row['kind']:<7}  "
            f"{row['commit']}{suffix}"
        )
    return "\n".join(lines)
