"""Console entry point: ``soliplex-skills <command>``.

Dispatches the subcommands that the per-skill ``skill_versions.py`` and build
scripts expose today, but driven by the consolidated library:

* ``list``    -- published versions of a skill (see :mod:`.versions`)
* ``diff``    -- installed skill vs. a published version
* ``upgrade`` -- install a published version in place
* ``build``   -- assemble/stamp/validate a skill into ``dist/``
  (see :mod:`.build`)

The ``list``/``diff``/``upgrade`` commands read each skill's
:class:`~soliplex_skills.versions.SkillSpec` from a ``[tool.soliplex-skills]``
stanza in ``pyproject.toml`` (see :mod:`.config`).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import abc
from pathlib import Path

from soliplex_skills import build
from soliplex_skills import config
from soliplex_skills.versions import SkillSpec
from soliplex_skills.versions import SkillVersions

_DIFF_DESCRIPTION = """\
Compare an installed skill against a published version, or two
published versions against each other.

With a single TARGET (default 'latest'), the skill at --skill-dir is
compared to that published version. Given two tags (TARGET OTHER),
those two published versions are compared to each other instead. What
is compared depends on the skill's compare_scope: the whole skill tree,
or only the references/ Markdown.

The diff is written to stdout: a per-file summary ('- removed',
'+ added', '~ changed'), followed by a unified diff of each changed
file unless --name-only is passed. 'No differences.' is printed when
the two sides match.\
"""

_DIFF_EPILOG = """\
exit status:
  0  the two sides are identical
  1  differences were found (and printed)
  2  invalid invocation (no --skill-dir and no second tag)\
"""


def _add_spec_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pyproject",
        type=Path,
        help="pyproject.toml with [tool.soliplex-skills] (default: search "
        "upward from the cwd).",
    )
    parser.add_argument(
        "--skill",
        help="skill name from the config (required if it defines several).",
    )


def _resolve_spec(args: argparse.Namespace) -> SkillSpec:
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
    rows = SkillVersions(_resolve_spec(args)).list(kind=args.kind)
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not rows:
        print("No published versions found.")
        return 0
    for row in rows:
        print(
            f"{row['tag']}  {row['date']}  {row['kind']:<7}  {row['commit']}"
        )
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
    return SkillVersions(_resolve_spec(args)).upgrade(
        args.skill_dir,
        args.target,
        force=args.force,
        dry_run=args.dry_run,
    )


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
            validate=not args.no_validate,
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="soliplex-skills")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List published skill versions.")
    _add_spec_args(p_list)
    p_list.add_argument("--kind", choices=["rolling", "release"])
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
        type=Path,
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
        "upgrade", help="Install a published version in place."
    )
    _add_spec_args(p_up)
    p_up.add_argument(
        "--skill-dir",
        required=True,
        type=Path,
        help="Installed skill root (the directory holding SKILL.md).",
    )
    p_up.add_argument("target", nargs="?", default="latest")
    p_up.add_argument("--force", action="store_true")
    p_up.add_argument("--dry-run", action="store_true")
    p_up.set_defaults(func=_cmd_upgrade)

    p_build = sub.add_parser(
        "build", help="Assemble/stamp/validate a skill into dist/."
    )
    p_build.add_argument("--src", required=True, type=Path)
    p_build.add_argument("--dist", required=True, type=Path)
    p_build.add_argument(
        "--skill", help="skill dir under src/ to build (default: all)."
    )
    p_build.add_argument("--commit")
    p_build.add_argument("--no-validate", action="store_true")
    p_build.set_defaults(func=_cmd_build)

    return parser


def main(argv: abc.Sequence[str] | None = None) -> int:
    """Parse *argv* and dispatch a subcommand; return a process exit code."""
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except config.SkillConfigError as exc:
        print(f"soliplex-skills: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
