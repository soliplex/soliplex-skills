# Skill anatomy

## On-disk layout

A built, installed skill is a self-contained directory:

```text
soliplex-docs/
├── SKILL.md              # frontmatter + body the agent reads
├── references/           # documentation / supporting material
├── scripts/
│   └── skill_versions.py # bundled list/diff/upgrade helper
└── assets/               # templates, etc. (skill-dependent)
```

`scripts/skill_versions.py` is the version-management helper bundled *inside*
the skill so it can manage its own installed copy without any external tooling.
It is a thin shim over the shared `soliplex-skills` library (see
[Managing an installed skill](../mechanisms/versions-cli.md)).

## `SKILL.md` frontmatter

`SKILL.md` opens with a YAML frontmatter block. The `metadata` table records
the build's identity:

```yaml
---
name: soliplex-docs
description: "…"
license: MIT
metadata:
  version: "0.68dev0"        # the skill's own version
  source_commit: "cc9a290"   # 7-char commit the build was assembled from
  generated: "2026-05-29"    # ISO build date
  source: https://github.com/soliplex/soliplex
---
```

- **`version`** — the skill's own version string. For a
  [repo-coupled skill](concepts.md#repo-coupled-vs-independently-versioned-skills)
  this tracks the repo; for an independently-versioned skill it advances on its
  own cadence.
- **`source_commit`** — the installed identity (see
  [Concepts](concepts.md#source_commit-the-installed-identity)). Stamped at
  build time; read back by clients to detect drift and skip no-op upgrades.
- **`generated`** — the build date, mirrored into the
  [release manifest](release-model.md#the-manifest).

!!! note "Stamping is a build step"
    The tracked source `SKILL.md` carries no `source_commit`. It is inserted
    only into the built copy under `dist/`, by
    [`metadata.stamp_source_commit`](../reference/api.md) during
    [building](../mechanisms/building.md).

## Where skills are installed

Filesystem skills are unpacked into an agent's skills directory — for Claude
Code, `~/.claude/skills/<skill-name>/`. There is no special installer step for
discovery: a running Soliplex scans its configured skill directories, reads
each `SKILL.md`'s frontmatter, and exposes the `metadata` table — so an
operator can see an installed skill's `source_commit` and compare it against
what is published.
