# Adopt in a new repo

This guide wires `soliplex-skills` into a fresh repository so that a filesystem
skill you maintain gets **versioned rolling and tagged releases** and can
**manage its own installed copy** (`list` / `diff` / `upgrade`).

It assumes you already have a skill source tree and adds three artifacts:

1. a bundled `scripts/skill_versions.py` shim — the in-skill manager,
2. a `scripts/build_skill.py` — assembles, stamps, and validates the skill,
3. a `.github/workflows/build-skill.yaml` — publishes it.

For the vocabulary (rolling build, tagged release, `…-latest` pointer) see
[Concepts](../overview/concepts.md) and the
[release model](../overview/release-model.md); each step below links to the
[Mechanisms](../mechanisms/building.md) page that explains the *why*.

Throughout, the running example is a single skill **`my-skill`**, released from
the GitHub repo **`my-org/my-repo`**. Substitute your own names — they must
agree across all four files.

## Prerequisites

- A skill source tree at `skills/my-skill/` containing a `SKILL.md` (plus
  `references/`, `scripts/`, `assets/` as needed). See
  [Skill anatomy](../overview/skill-anatomy.md).
- [`uv`](https://docs.astral.sh/uv/) for running the scripts.
- A GitHub repository whose Actions can publish releases
  (`permissions: contents: write`).

The layout this guide produces:

```text
my-repo/
├── pyproject.toml
├── scripts/
│   └── build_skill.py
├── skills/
│   └── my-skill/
│       ├── SKILL.md
│       └── scripts/
│           └── skill_versions.py
└── .github/
    └── workflows/
        └── build-skill.yaml
```

## Step 1 — the in-skill shim

`skills/my-skill/scripts/skill_versions.py` is bundled *inside* the skill so an
agent (or a human) can [manage the installed copy](../mechanisms/versions-cli.md)
without any external tooling. Because an installed skill runs where neither the
library nor your `pyproject.toml` is present, it is a self-contained
[PEP 723](https://peps.python.org/pep-0723/) script: the inline
`# dependencies` block lets `uv` provision `soliplex-skills` at run time, and
the per-skill identity is hard-coded into a `SkillSpec`. Everything else is the
shared library — this file is [a thin shim](../mechanisms/versions-cli.md#library-api).

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["soliplex-skills>=0.5"]
# ///
"""List, diff, and upgrade published ``my-skill`` versions.

This script is bundled inside the skill (under ``scripts/``) so an agent -- or
a human -- can manage the installed copy without leaving the skill:

* ``list``    -- which versions have been published? Rolling builds
  (``my-skill-YYYY.MM.DD-<sha>``) and release snapshots are shown newest-first,
  with the installed copy and the current ``latest`` pointer marked.
* ``diff``    -- how does the installed skill differ from a published version
  (default: ``latest``)? Pass two tags to compare them against each other
  instead.
* ``upgrade`` -- download a published version (default: ``latest``) and install
  it in place, so files deleted upstream do not linger.

The logic lives in the shared ``soliplex-skills`` library; this script is a
thin shim that fills in the skill's identity and delegates.

Run this script with ``uv`` so that dependency is provisioned automatically:

    uv run scripts/skill_versions.py list

Network access to ``api.github.com`` / ``github.com`` is needed; set
``GITHUB_TOKEN`` or ``GH_TOKEN`` to raise the API rate limit.
"""

from __future__ import annotations

import argparse
import json
import re
import pathlib
import sys

from soliplex_skills import versions

# The skill root is the parent of this script's ``scripts/`` directory.
SKILL_ROOT = pathlib.Path(__file__).resolve().parent.parent

# The only values that distinguish this skill from any other; everything else
# is handled by the library.
SPEC = versions.SkillSpec(
    owner="my-org",
    repo="my-repo",
    skill_name="my-skill",
    asset_tarball="my-skill.tar.gz",
    pointer_tag="my-skill-latest",
    rolling_re=re.compile(r"^my-skill-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"),
)


def cmd_list(args: argparse.Namespace) -> int:
    rows = versions.SkillVersions(SPEC).list(
        kind=args.kind, installed_path=SKILL_ROOT, mark_latest=True
    )
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(versions.format_list_table(rows))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    skill_versions = versions.SkillVersions(SPEC)
    if args.other is not None:
        return skill_versions.diff_published(
            args.target, args.other, name_only=args.name_only
        )
    return skill_versions.diff(
        SKILL_ROOT, args.target, name_only=args.name_only
    )


def cmd_upgrade(args: argparse.Namespace) -> int:
    return versions.SkillVersions(SPEC).upgrade(
        SKILL_ROOT, args.tag, force=args.force, dry_run=args.dry_run
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List published skill versions.")
    p_list.add_argument(
        "--kind",
        choices=["rolling", "release"],
        help="Show only rolling builds or only software-release builds.",
    )
    p_list.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    p_list.set_defaults(func=cmd_list)

    p_diff = sub.add_parser(
        "diff",
        help="Diff the installed skill against a published version, or two "
        "published versions against each other.",
    )
    p_diff.add_argument(
        "target",
        nargs="?",
        default="latest",
        help="Version tag to compare against (default: latest).",
    )
    p_diff.add_argument(
        "other",
        nargs="?",
        help="Optional second tag: diff 'target' against 'other' instead "
        "of against the installed skill.",
    )
    p_diff.add_argument(
        "--name-only",
        action="store_true",
        help="List changed files without printing unified diffs.",
    )
    p_diff.set_defaults(func=cmd_diff)

    p_upgrade = sub.add_parser(
        "upgrade",
        help="Download a published version and install it in place.",
    )
    p_upgrade.add_argument(
        "tag",
        nargs="?",
        default="latest",
        help="Version tag to upgrade to (default: latest).",
    )
    p_upgrade.add_argument(
        "--force",
        action="store_true",
        help="Reinstall even when the installed copy is already current.",
    )
    p_upgrade.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be installed without writing any files.",
    )
    p_upgrade.set_defaults(func=cmd_upgrade)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except versions.PointerUnavailable as exc:
        print(f"skill_versions: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: NO COVER
    sys.exit(main())
```

The `rolling_re` here must match the `rolling_prefix` you record in
`pyproject.toml` ([Step 4](#step-4-pyprojecttoml)).

### Document the shim in `SKILL.md`

The shim is only discoverable if `SKILL.md` mentions it. Append a short
**`## Managing this skill`** epilogue so an agent (or human) reading the
installed skill knows the self-management commands exist. This is the exemplar
to copy into `skills/my-skill/SKILL.md` — adjust the wording, but keep the
`##` heading and the reference to `scripts/skill_versions.py`:

```markdown
## Managing this skill

This skill can manage its own installed copy via the bundled
`scripts/skill_versions.py` helper. Run it with `uv` (which provisions its one
dependency automatically):

- **list** published versions, newest first, with the installed copy and the
  current `latest` pointer marked:

      uv run scripts/skill_versions.py list

- **diff** the installed copy against a published version (default `latest`;
  pass two tags to compare them with each other instead):

      uv run scripts/skill_versions.py diff

- **upgrade** the installed copy in place to a published version (default
  `latest`), so files deleted upstream do not linger:

      uv run scripts/skill_versions.py upgrade

Network access to `github.com` is required; set `GITHUB_TOKEN` or `GH_TOKEN`
to raise the API rate limit.
```

!!! note "Installing into a Soliplex stack"
    When this skill is installed into a Soliplex stack with
    [`soliplex-skills install --defang`](../mechanisms/installation.md#the-install-cli-command),
    the installer removes `scripts/skill_versions.py` and rewrites this
    `##` section to a short note — it locates the section by finding the
    `##` heading whose body mentions `skill_versions.py`. A room agent cannot
    drive the self-management commands, so they are stripped rather than left
    dangling; the copy is then updated from the outside by re-running the
    installer. Keeping the heading and the `scripts/skill_versions.py`
    reference is what lets the installer find and defang this section.

## Step 2 — the build script

`scripts/build_skill.py` is a thin wrapper over
[`build.build_skill`](../mechanisms/building.md#api): it copies
`skills/my-skill/` into `dist/my-skill/`, stamps `SKILL.md` with the source
commit, and validates the result with the `skills-ref` library. Packaging is
the workflow's job ([Step 3](#step-3-the-publish-workflow)); `dist/` is
gitignored.

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["soliplex-skills>=0.5"]
# ///
"""Assemble and validate the my-skill skill into dist/.

Thin wrapper over ``soliplex_skills.build.build_skill``:

- copies ``skills/my-skill/`` to ``dist/my-skill/``
- stamps ``SKILL.md`` with the source commit (``--commit``, default git HEAD)
- validates with the ``skills-ref`` library.

Packaging is the CI workflow's job; ``dist/`` is gitignored.

    uv run scripts/build_skill.py
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from soliplex_skills import build

SKILL_NAME = "my-skill"
REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_DIR / "skills"
DIST = REPO_DIR / "dist"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble + validate the skill."
    )
    parser.add_argument(
        "--commit",
        help="Commit to stamp into SKILL.md metadata (default: git HEAD).",
    )
    args = parser.parse_args(argv)

    try:
        out = build.build_skill(
            SKILL_NAME, src=SKILLS_DIR, dist=DIST, commit=args.commit
        )
    except (build.SkillNotFound, build.ValidationFailed) as exc:
        print(f"build_skill: error: {exc}", file=sys.stderr)
        return 1

    print(f"built & validated: {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

### Variations

??? note "Several skills in one repo"
    Drop the single `SKILL_NAME` and let
    [`build.discover_skills`](../mechanisms/building.md#api) find every
    `skills/<name>/` (those with a `SKILL.md`), with `--skill` to build just
    one. Resolve the commit once with `build.git_head_commit`:

    ```python
    names = [args.skill] if args.skill else build.discover_skills(SKILLS_DIR)
    commit = args.commit or build.git_head_commit(REPO_DIR)
    for name in names:
        out = build.build_skill(name, src=SKILLS_DIR, dist=DIST, commit=commit)
    ```

??? note "Generating content at build time"
    To assemble part of the skill during the build (for example, a docs skill
    that copies a `docs/` tree into `references/`), pass a `generator`
    callback. It runs after the commit stamp and before validation, so what it
    writes is part of the validated skill:

    ```python
    def add_content(out_dir: pathlib.Path) -> None:
        # write/replace files under out_dir (the dist/<name>/ copy)
        ...

    build.build_skill(
        SKILL_NAME, src=SKILLS_DIR, dist=DIST, commit=commit,
        generator=add_content,
    )
    ```

## Step 3 — the publish workflow

`.github/workflows/build-skill.yaml` runs the build script, then publishes the
result. It has two modes (see [Publishing a skill](../mechanisms/publishing.md)):

- on a **software release**, it attaches the skill snapshot to that release;
- on **skill changes to `main`** (and manual dispatch), it publishes an
  immutable rolling build `my-skill-YYYY.MM.DD-<sha>`, repoints the
  `my-skill-latest` pointer (with a `latest.json` manifest) at it, and prunes
  old rolling builds to `KEEP_ROLLING`.

The skill-specific values live in `env:` at the top — change those and the rest
is reusable as-is.

```yaml
name: Build & publish my-skill skill

on:
  release:
    types: [published]
  push:
    branches: [main]
    paths:
      - 'skills/my-skill/**'
      - 'scripts/build_skill.py'
      - '.github/workflows/build-skill.yaml'
  workflow_dispatch:

# Serialize publishes so concurrent runs do not race on the rolling pointer
# or the prune step.
concurrency:
  group: build-skill
  cancel-in-progress: false

env:
  DIST: dist
  SKILL_DIR: my-skill
  ASSET_TARBALL: my-skill.tar.gz
  ASSET_ZIP: my-skill.zip
  POINTER_TAG: my-skill-latest
  KEEP_ROLLING: "10"

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v6

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version-file: "pyproject.toml"

      # The 'dev' group provides 'skills-ref' (skill validation), which
      # build_skill.py uses via soliplex-skills.
      - name: Install dependencies
        run: uv sync --frozen --group dev

      - name: Build & validate skill
        run: uv run --group dev python scripts/build_skill.py --commit "${{ github.sha }}"

      # All release assets are written under dist/ (gitignored) alongside the
      # assembled skill directory.
      - name: Package skill
        run: |
          tar czf "$DIST/$ASSET_TARBALL" -C "$DIST" "$SKILL_DIR"
          (cd "$DIST" && zip -qr "$ASSET_ZIP" "$SKILL_DIR")

      - name: Compute build identity
        run: |
          {
            echo "SHORT_SHA=${GITHUB_SHA::7}"
            echo "GEN_DATE=$(date -u +%Y-%m-%d)"
            echo "ROLLING_TAG=my-skill-$(date -u +%Y.%m.%d)-${GITHUB_SHA::7}"
            echo "SHA256=$(sha256sum "$DIST/$ASSET_TARBALL" | cut -d' ' -f1)"
          } >> "$GITHUB_ENV"

      # version.json identifies a published build so consumers can detect
      # drift and verify the download. Written for whichever tag we publish.
      - name: Write version manifest
        env:
          TARGET_TAG: ${{ github.event_name == 'release' && github.event.release.tag_name || env.ROLLING_TAG }}
        run: |
          jq -n \
            --arg tag "$TARGET_TAG" \
            --arg commit "$SHORT_SHA" \
            --arg generated "$GEN_DATE" \
            --arg sha256 "$SHA256" \
            --arg url "https://github.com/${GITHUB_REPOSITORY}/releases/download/${TARGET_TAG}/${ASSET_TARBALL}" \
            '{tag:$tag, source_commit:$commit, generated:$generated, sha256:$sha256, asset_url:$url}' \
            > "$DIST/version.json"
          cat "$DIST/version.json"

      # --- Software-release mode -------------------------------------------
      - name: Attach skill to software release
        if: github.event_name == 'release'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          TAG: ${{ github.event.release.tag_name }}
        run: >
          gh release upload "$TAG"
          "$DIST/$ASSET_TARBALL" "$DIST/$ASSET_ZIP" "$DIST/version.json" --clobber

      # --- Rolling mode ----------------------------------------------------
      - name: Publish immutable rolling build
        if: github.event_name != 'release'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release view "$ROLLING_TAG" >/dev/null 2>&1 || \
            gh release create "$ROLLING_TAG" \
              --prerelease \
              --target "$GITHUB_SHA" \
              --title "my-skill $ROLLING_TAG" \
              --notes "Rolling my-skill Agent Skill built from ${GITHUB_SHA}."
          gh release upload "$ROLLING_TAG" \
            "$DIST/$ASSET_TARBALL" "$DIST/$ASSET_ZIP" "$DIST/version.json" --clobber

      - name: Update 'latest' pointer
        if: github.event_name != 'release'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release view "$POINTER_TAG" >/dev/null 2>&1 || \
            gh release create "$POINTER_TAG" \
              --prerelease \
              --title "my-skill (latest)" \
              --notes "Rolling pointer to the newest my-skill Agent Skill build."
          # latest.json points at the immutable build; the tarball/zip are
          # re-hosted here too so the pointer URL is a one-request download.
          cp "$DIST/version.json" "$DIST/latest.json"
          gh release upload "$POINTER_TAG" \
            "$DIST/latest.json" "$DIST/$ASSET_TARBALL" "$DIST/$ASSET_ZIP" --clobber

      - name: Prune old rolling builds
        if: github.event_name != 'release'
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release list --limit 200 --json tagName --jq '.[].tagName' \
            | grep -E '^my-skill-[0-9]{4}\.' \
            | sort -r \
            | tail -n +$((KEEP_ROLLING + 1)) \
            | while read -r tag; do
                echo "Pruning $tag"
                gh release delete "$tag" --cleanup-tag --yes
              done
```

??? note "Several skills in one repo"
    Publish each skill on its own tag namespace by running the workflow once
    per skill with a `matrix:`, moving the per-skill values into the matrix and
    referencing them as `${{ matrix.* }}`:

    ```yaml
    strategy:
      fail-fast: false
      matrix:
        include:
          - name: my-skill
            prefix: my-skill
            tarball: my-skill.tar.gz
            zip: my-skill.zip
          - name: my-other-skill
            prefix: my-other-skill
            tarball: my-other-skill.tar.gz
            zip: my-other-skill.zip

    concurrency:
      group: build-skills-${{ matrix.prefix }}
      cancel-in-progress: false
    ```

    The build step then targets one skill —
    `python scripts/build_skill.py --skill "${{ matrix.name }}"
    --commit "${{ github.sha }}"` — and the prune step matches only that
    skill's rolling tags (`^${{ matrix.prefix }}-[0-9]{4}\.`).

## Step 4 — `pyproject.toml`

Add `soliplex-skills` to your dev dependencies (it pulls in `skills-ref`, the
skill validator, transitively):

```toml
[dependency-groups]
dev = [
    "pytest",
    "ruff",
    "soliplex-skills >= 0.5",
]
```

Record the skill once in a `[[tool.soliplex-skills.skill]]` stanza. This lets
the [`soliplex-skills` console script](../mechanisms/versions-cli.md#cli-configuration)
(and CI) manage the published skill without repeating the constants on the
command line:

```toml
# The bundled scripts/skill_versions.py hard-codes the same values, since it
# cannot read this file once the skill is installed elsewhere.
[[tool.soliplex-skills.skill]]
name = "my-skill"
owner = "my-org"
repo = "my-repo"
asset_tarball = "my-skill.tar.gz"
pointer_tag = "my-skill-latest"
rolling_prefix = "my-skill"      # -> ^my-skill-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$
```

The `rolling_prefix` here mirrors the shim's `rolling_re` from
[Step 1](#step-1-the-in-skill-shim) — keep them in sync.

If you gate on test coverage, exempt the bundled shim (it is exercised by the
library's own suite):

```toml
[tool.coverage.run]
omit = [
    "*/skills/*/scripts/skill_versions.py",
]
```

## Verify

```console
# Build + validate locally (writes dist/my-skill/, stamped & validated):
$ uv run scripts/build_skill.py
built & validated: /path/to/my-repo/dist/my-skill

# Once published, the shim resolves versions over the GitHub API:
$ uv run skills/my-skill/scripts/skill_versions.py list

# Or drive the same operations from the console script via the config stanza:
$ uv run soliplex-skills list --skill my-skill
```

Push the three files to `main` (touching `skills/my-skill/**`) to trigger the
workflow's rolling build, or cut a software release to attach a pinned
snapshot. The [API reference](../reference/api.md) is the full library surface
behind these examples.
