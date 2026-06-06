# Concepts & vocabulary

This page defines the terms used throughout the rest of the site.

## Filesystem skill

A skill in the [agentskills.io](https://agentskills.io) sense: a directory an
agent (or a human) drops onto disk. Its **skill root** is the directory
containing `SKILL.md`:

```text
soliplex-docs/
├── SKILL.md          # frontmatter (name, description, …) + body
├── references/       # docs / supporting material the skill reads
├── scripts/          # helper scripts bundled with the skill
└── assets/           # templates and other files (optional)
```

`SKILL.md` opens with a YAML frontmatter block. Its `metadata` table is where
this project records a build's identity — see
[Skill anatomy](skill-anatomy.md).

## `source_commit` — the installed identity

When a skill is built for release, the commit it was assembled from is stamped
into `SKILL.md` as `metadata.source_commit` (a 7-character short SHA). That is
the **installed identity**: clients read it back to decide whether the
installed skill matches a given published build, and whether an upgrade is a
no-op.

A skill's *tracked* source `SKILL.md` is deliberately left **unstamped** — only
the built copy under `dist/` carries a `source_commit`.

## Rolling build vs. tagged release

A skill is published in two flavors:

- **Rolling build** — an automatic, immutable snapshot cut on every change to
  the skill's sources. Its tag is dated: `<prefix>-YYYY.MM.DD-<sha7>`, e.g.
  `docs-2026.05.29-cc9a290f`. Rolling builds track the bleeding edge and are
  pruned to a fixed retention count.
- **Tagged release** — an explicit, curated snapshot meant to be referenced by
  a stable version. *Which tag it lands on* depends on how the skill is
  versioned (next section).

## Repo-coupled vs. independently-versioned skills

This distinction decides where a **tagged release** is published:

- A **repo-coupled skill** has a version that tracks its source repository — it
  ships *with* the repo (for example, `soliplex-docs` packages the `soliplex`
  repo's own documentation). Its tagged release rides the repo's own software
  release tag (`v…`).
- An **independently-versioned skill** advances its `metadata.version` on its
  own cadence, decoupled from the repo's version. Its tagged release is
  published under the skill's **own tag namespace** — e.g.
  `<skill>-vX.Y.Z` — rather than being bundled onto the repo's `v…` release.

The payoff: one repository can host several skills versioned on different
schedules, and a skill's published version line stays independent of the
repo's release history. The [release model](release-model.md) shows both paths.

## The `…-latest` pointer and `latest.json`

So a client can answer *"what is the newest build?"* in a single request,
each skill publishes a stable **pointer tag** — `<prefix>-latest` (e.g.
`docs-latest`). That tag carries a small **`latest.json`** manifest (plus a
copy of the asset) describing whatever the newest rolling build is. The
manifest schema is shared by the publishing workflow and every client; see
[`ReleaseManifest`](../reference/api.md).
