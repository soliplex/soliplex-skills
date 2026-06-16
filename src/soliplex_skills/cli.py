"""Console entry point: ``soliplex-skills <command>``.

The installed console script. It dispatches:

* ``list``    -- published versions of a skill (see :mod:`.versions`)
* ``diff``    -- installed skill vs. a published version
* ``upgrade`` -- install a published version in place
* ``download`` -- download + extract a published skill to a local directory
  (see :mod:`.install`)
* ``install`` -- install a skill into a stack, optionally defanged, from a
  published release or a local ``--source-dir`` (see :mod:`.install`)
* ``build``   -- assemble/stamp/validate a skill into ``dist/``
  (see :mod:`.build`)

The ``list``/``diff``/``upgrade``/``install``/``download`` commands read each
skill's
:class:`~soliplex_skills.versions.SkillSpec` from a ``[tool.soliplex-skills]``
stanza in ``pyproject.toml`` (see :mod:`.config`).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import abc

from soliplex_skills import build
from soliplex_skills import config
from soliplex_skills import install
from soliplex_skills.versions import SkillSpec
from soliplex_skills.versions import SkillVersions
from soliplex_skills.versions import format_list_table

_DIFF_DESCRIPTION = """\
Compare an installed skill against a published version, or two
published versions against each other.

With a single TARGET (default 'latest'), the skill at --skill-dir is
compared to that published version. Given two tags (TARGET OTHER),
those two published versions are compared to each other instead. The
whole skill tree is compared; the per-build source_commit stamp in
SKILL.md is ignored.

The diff is written to stdout: a per-file summary ('- removed',
'+ added', '~ changed'), followed by a unified diff of each changed
file unless --name-only is passed. 'No differences.' is printed when
the two sides match.\
"""

_DIFF_EPILOG = """\
exit status:
  0  the two sides are identical
  1  differences were found (and printed)
  2  invalid invocation, or invalid skill configuration\
"""

_LIST_DESCRIPTION = """\
List a skill's published versions, newest first.

Shows both rolling builds and tagged releases that carry the skill's
release asset; the '...-latest' pointer tag is excluded. Filter with
--kind. By default a table is printed -- TAG, DATE (published), KIND
('rolling' or 'release'), and the 7-char source COMMIT -- one row per
version, or 'No published versions found.' when there are none. The
row matching --skill-dir is marked 'installed' and the row the
'latest' pointer resolves to is marked 'latest'. Pass --json to emit
the same rows (each with 'prerelease', 'installed', and 'latest'
flags) as a JSON array.\
"""

_LIST_EPILOG = """\
exit status:
  0  versions listed (or none are published)
  2  invalid skill configuration\
"""

_UPGRADE_DESCRIPTION = """\
Install a published version (or a local --source-dir) over --skill-dir.

TARGET is a tag or 'latest' (the default, resolved via the skill's
pointer manifest); the download's sha256 is verified against the
manifest when known. Pass --source-dir to upgrade from an
already-extracted local copy instead of downloading. Files are replaced
in place -- directories removed first -- so files deleted upstream do
not linger. If the installed source_commit already matches it is a
no-op unless --force is given. Upgrade refuses a de-novo install (use
'install' when the skill is not yet present). --dry-run reports the
plan on stdout without writing anything.\
"""

_UPGRADE_EPILOG = """\
exit status:
  0  upgraded, or already up to date (a no-op)
  2  invalid skill configuration\
"""

_INSTALL_DESCRIPTION = """\
Install a skill under --dest, from a published release or a local copy.

The skill lands in <dest>/<name>/. By default it is downloaded: TARGET
is a tag or 'latest' (resolved via the skill's pointer manifest) and
the download's sha256 is verified against the manifest when known.
Pass --source-dir instead to install an already-extracted local copy
(offline / development); it is validated against the agent-skills spec
and the source directory is never modified. The skill is always
installed under its own name (the validator requires the directory name
to match). The skill is installed over any existing copy -- directories
removed first
-- so files deleted upstream do not linger. An existing copy whose
source_commit already matches the target is left untouched unless
--force is given. With --defang the bundled scripts/skill_versions.py
self-management helper and the SKILL.md section documenting it are
stripped, so the copy is safe to run inside a Soliplex room agent.
--dry-run reports the plan without writing anything (and, for a
download, without fetching the asset).\
"""

_INSTALL_EPILOG = """\
exit status:
  0  installed, upgraded, or already up to date (a no-op)
  2  invalid invocation, or invalid skill configuration\
"""

_DOWNLOAD_DESCRIPTION = """\
Download + extract a published skill to a local directory.

The skill tree lands in <dest>/<name>/. TARGET is a tag or 'latest'
(the default, resolved via the skill's pointer manifest); the
download's sha256 is verified against the manifest when known. A
non-empty target directory is left untouched unless --force is given.
Nothing is defanged -- this is the raw published artifact, ready to
feed back to 'install --source-dir <dest>/<name>'.\
"""

_DOWNLOAD_EPILOG = """\
exit status:
  0  downloaded
  2  invalid skill configuration\
"""

_BUILD_DESCRIPTION = """\
Assemble, stamp, and validate skill(s) into a distribution directory.

Copies each skill under --src into <dist>/<name>/ (skipping
__pycache__) and stamps its SKILL.md metadata with the source commit
(--commit, defaulting to the source tree's git HEAD), the build date
(--date, defaulting to today), and -- when given -- the published
--version (omit it for rolling builds). Unless --no-validate, the
agent-skills validator is then run. With --skill only that one skill is
built; otherwise every skill directory under --src is built.\
"""

_BUILD_EPILOG = """\
exit status:
  0  all skills built
  1  no skills found under --src\
"""


def _add_spec_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--project",
        type=pathlib.Path,
        help="A pyproject.toml with [tool.soliplex-skills], or a directory "
        "containing one, to read the skill config from (default: search "
        "upward from the cwd).",
    )
    parser.add_argument(
        "--pyproject",
        type=pathlib.Path,
        help="Deprecated alias for --project, accepting a pyproject.toml file "
        "only; --project takes precedence.",
    )
    parser.add_argument(
        "--skill",
        help="skill name from the config (required if it defines several).",
    )


def _pyproject_from_project(project: pathlib.Path) -> pathlib.Path:
    """Resolve a ``--project`` path to its ``pyproject.toml``.

    *project* may be the ``pyproject.toml`` file itself or a directory
    containing one. Raises :class:`config.PyprojectNotFound` if no file is
    found there.
    """
    path = project / "pyproject.toml" if project.is_dir() else project
    if not path.is_file():
        raise config.PyprojectNotFound(project)
    return path


def _resolve_spec(args: argparse.Namespace) -> SkillSpec:
    if args.project is not None:
        pyproject = _pyproject_from_project(args.project)
    else:
        pyproject = args.pyproject or config.find_pyproject()
    specs = config.load_skill_specs(pyproject)
    if args.skill:
        if args.skill not in specs:
            raise config.UnknownSkill(args.skill, sorted(specs))
        return specs[args.skill]
    if len(specs) == 1:
        return next(iter(specs.values()))
    raise config.AmbiguousSkill(sorted(specs))


def _cmd_list(args: argparse.Namespace) -> int:
    rows = SkillVersions(_resolve_spec(args)).list(
        kind=args.kind,
        installed_path=args.skill_dir,
        mark_latest=True,
    )
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(format_list_table(rows))
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    versions = SkillVersions(_resolve_spec(args))
    if args.other is not None:
        return versions.diff_published(
            args.target, args.other, name_only=args.name_only
        )
    if args.skill_dir is None:
        print(
            "soliplex-skills: error: diff needs --skill-dir (or a second "
            "tag to compare two published versions).",
            file=sys.stderr,
        )
        return 2
    return versions.diff(args.skill_dir, args.target, name_only=args.name_only)


def _cmd_upgrade(args: argparse.Namespace) -> int:
    if args.source_dir is not None and (
        args.skill or args.project or args.pyproject
    ):
        print(
            "soliplex-skills: error: --source-dir cannot be combined with "
            "a published-skill selector (--skill/--project/--pyproject).",
            file=sys.stderr,
        )
        return 2
    # Default (--defang omitted): preserve the installed skill's defang state.
    defang = (
        install.is_defanged(args.skill_dir)
        if args.defang is None
        else args.defang
    )
    dest = args.skill_dir.parent
    try:
        if args.source_dir is not None:
            skill_root, status = install.upgrade_skill_from(
                args.source_dir,
                dest,
                installed_by=_DEFAULT_INSTALLED_BY,
                defang=defang,
                force=args.force,
                dry_run=args.dry_run,
            )
        else:
            spec = _published_from_spec(_resolve_spec(args))
            version = None if args.target == "latest" else args.target
            skill_root, status = install.upgrade_skill(
                spec,
                version,
                dest,
                installed_by=_DEFAULT_INSTALLED_BY,
                defang=defang,
                force=args.force,
                dry_run=args.dry_run,
            )
    except install.NotInstalled as exc:
        print(f"soliplex-skills: error: {exc}", file=sys.stderr)
        return 2
    name = skill_root.name
    if status is install.InstallStatus.UNCHANGED:
        print(f"Already up to date: {name} at {skill_root}.")
    elif args.dry_run:
        print(f"Would upgrade {name} at {skill_root}.")
    else:
        print(f"Upgraded {name} at {skill_root}.")
    return 0


def _published_from_spec(spec: SkillSpec) -> install.PublishedSkill:
    """Adapt a config :class:`SkillSpec` to an ``install.PublishedSkill``."""
    return install.PublishedSkill(
        name=spec.skill_name,
        owner=spec.owner,
        repo=spec.repo,
        asset_tarball=spec.asset_tarball,
        pointer_tag=spec.pointer_tag,
        pointer_manifest=spec.pointer_manifest,
    )


#: Default recorded in a defanged skill's note when no installer is named.
_DEFAULT_INSTALLED_BY = "soliplex-skills"

_INSTALL_MESSAGES = {
    install.InstallStatus.ADDED: "Installed {name} into {root}.",
    install.InstallStatus.REINSTALLED: "Reinstalled {name} at {root}.",
    install.InstallStatus.UNCHANGED: "Already up to date: {name} at {root}.",
}


def _cmd_download(args: argparse.Namespace) -> int:
    spec = _published_from_spec(_resolve_spec(args))
    version = None if args.target == "latest" else args.target
    try:
        root = install.download_skill(
            spec, version, args.dest, force=args.force
        )
    except install.DestinationNotEmpty as exc:
        print(f"soliplex-skills: error: {exc}", file=sys.stderr)
        return 2
    print(f"Downloaded {spec.name} to {root}.")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    if args.source_dir is not None and (
        args.skill or args.project or args.pyproject
    ):
        print(
            "soliplex-skills: error: --source-dir cannot be combined with "
            "a published-skill selector (--skill/--project/--pyproject).",
            file=sys.stderr,
        )
        return 2
    try:
        if args.source_dir is not None:
            skill_root, status = install.install_skill_from(
                args.source_dir,
                args.dest,
                installed_by=args.installed_by,
                defang=args.defang,
                force=args.force,
                dry_run=args.dry_run,
            )
        else:
            spec = _published_from_spec(_resolve_spec(args))
            version = None if args.target == "latest" else args.target
            skill_root, status = install.install_skill(
                spec,
                version,
                args.dest,
                installed_by=args.installed_by,
                defang=args.defang,
                force=args.force,
                dry_run=args.dry_run,
            )
    except install.VersionMismatch as exc:
        print(f"soliplex-skills: error: {exc}", file=sys.stderr)
        return 2
    name = skill_root.name
    if args.dry_run:
        print(f"Would install {name} into {skill_root}.")
    else:
        print(_INSTALL_MESSAGES[status].format(name=name, root=skill_root))
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    names = [args.skill] if args.skill else build.discover_skills(args.src)
    if not names:
        print(f"no skills found under {args.src}", file=sys.stderr)
        return 1
    for name in names:
        build.build_skill(
            name,
            src=args.src,
            dist=args.dist,
            commit=args.commit,
            version=args.version,
            generated=args.date,
            validate=not args.no_validate,
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soliplex-skills")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser(
        "list",
        help="List published skill versions.",
        description=_LIST_DESCRIPTION,
        epilog=_LIST_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_spec_args(p_list)
    p_list.add_argument(
        "--skill-dir",
        type=pathlib.Path,
        help="Installed skill root (the directory holding SKILL.md); its "
        "matching row is flagged 'installed'.",
    )
    p_list.add_argument(
        "--kind",
        choices=["rolling", "release"],
        help="Show only rolling builds or only tagged releases.",
    )
    p_list.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    p_list.set_defaults(func=_cmd_list)

    p_diff = sub.add_parser(
        "diff",
        help="Diff an installed skill against a published version, or two "
        "published versions against each other.",
        description=_DIFF_DESCRIPTION,
        epilog=_DIFF_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_spec_args(p_diff)
    p_diff.add_argument(
        "--skill-dir",
        type=pathlib.Path,
        help="Installed skill root (the directory holding SKILL.md); "
        "required unless two published tags are given.",
    )
    p_diff.add_argument(
        "target",
        nargs="?",
        default="latest",
        help="Published version to compare against: a tag, or 'latest' "
        "(the default).",
    )
    p_diff.add_argument(
        "other",
        nargs="?",
        help="Second published tag; when given, compare TARGET vs OTHER "
        "instead of the installed skill.",
    )
    p_diff.add_argument(
        "--name-only",
        action="store_true",
        help="List only the changed/added/removed files; omit the unified "
        "diff.",
    )
    p_diff.set_defaults(func=_cmd_diff)

    p_up = sub.add_parser(
        "upgrade",
        help="Install a published version in place.",
        description=_UPGRADE_DESCRIPTION,
        epilog=_UPGRADE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_spec_args(p_up)
    p_up.add_argument(
        "--skill-dir",
        required=True,
        type=pathlib.Path,
        help="Installed skill root (the directory holding SKILL.md).",
    )
    p_up.add_argument(
        "--source-dir",
        type=pathlib.Path,
        help="Upgrade from this local skill directory (validated against the "
        "agent-skills spec) instead of downloading; mutually exclusive with "
        "the published-skill selectors.",
    )
    p_up.add_argument(
        "target",
        nargs="?",
        default="latest",
        help="Published version to install: a tag, or 'latest' (the default).",
    )
    p_up.add_argument(
        "--defang",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Strip (--defang) or keep (--no-defang) the self-management "
        "helper. Default: match the existing installed skill's state.",
    )
    p_up.add_argument(
        "--force",
        action="store_true",
        help="Reinstall even when the installed commit already matches "
        "TARGET.",
    )
    p_up.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be installed without writing anything.",
    )
    p_up.set_defaults(func=_cmd_upgrade)

    p_install = sub.add_parser(
        "install",
        help="Install a published skill into a stack (optionally defanged).",
        description=_INSTALL_DESCRIPTION,
        epilog=_INSTALL_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_spec_args(p_install)
    p_install.add_argument(
        "--dest",
        required=True,
        type=pathlib.Path,
        help="Directory the skill is installed under, as <dest>/<name>/.",
    )
    p_install.add_argument(
        "--source-dir",
        type=pathlib.Path,
        help="Install from this local skill directory (validated against the "
        "agent-skills spec) instead of downloading; mutually exclusive with "
        "the published-skill selectors.",
    )
    p_install.add_argument(
        "target",
        nargs="?",
        default="latest",
        help="Published version to install: a tag, or 'latest' (the default).",
    )
    p_install.add_argument(
        "--installed-by",
        default=_DEFAULT_INSTALLED_BY,
        help="Name of the installer recorded in the defang note (only used "
        f"with --defang; default: {_DEFAULT_INSTALLED_BY!r}).",
    )
    p_install.add_argument(
        "--defang",
        action="store_true",
        help="Strip the scripts/skill_versions.py self-management helper and "
        "its SKILL.md section (default: keep them).",
    )
    p_install.add_argument(
        "--force",
        action="store_true",
        help="Reinstall even when the installed commit already matches "
        "TARGET.",
    )
    p_install.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be installed without writing anything.",
    )
    p_install.set_defaults(func=_cmd_install)

    p_download = sub.add_parser(
        "download",
        help="Download + extract a published skill to a local directory.",
        description=_DOWNLOAD_DESCRIPTION,
        epilog=_DOWNLOAD_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_spec_args(p_download)
    p_download.add_argument(
        "--dest",
        required=True,
        type=pathlib.Path,
        help="Directory the skill is downloaded into, as <dest>/<name>/.",
    )
    p_download.add_argument(
        "target",
        nargs="?",
        default="latest",
        help="Published version: a tag, or 'latest' (the default).",
    )
    p_download.add_argument(
        "--force",
        action="store_true",
        help="Replace the target directory even when it is not empty.",
    )
    p_download.set_defaults(func=_cmd_download)

    p_build = sub.add_parser(
        "build",
        help="Assemble/stamp/validate a skill into dist/.",
        description=_BUILD_DESCRIPTION,
        epilog=_BUILD_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_build.add_argument(
        "--src",
        required=True,
        type=pathlib.Path,
        help="Directory containing the skill source tree(s).",
    )
    p_build.add_argument(
        "--dist",
        required=True,
        type=pathlib.Path,
        help="Output directory; each skill lands in <dist>/<name>/.",
    )
    p_build.add_argument(
        "--skill", help="skill dir under src/ to build (default: all)."
    )
    p_build.add_argument(
        "--commit",
        help="Source commit to stamp into SKILL.md (default: git HEAD).",
    )
    p_build.add_argument(
        "--version",
        help="Published version to stamp into SKILL.md (omit for rolling "
        "builds).",
    )
    p_build.add_argument(
        "--date",
        help="Build date (ISO YYYY-MM-DD) to stamp as 'generated' (default: "
        "today).",
    )
    p_build.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip the agent-skills validation step.",
    )
    p_build.set_defaults(func=_cmd_build)

    return parser


def main(argv: abc.Sequence[str] | None = None) -> int:
    """Parse *argv* and dispatch a subcommand; return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (config.SkillConfigError, install.SourceInvalid) as exc:
        print(f"soliplex-skills: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
