# Soliplex Skills

`soliplex-skills` is shared infrastructure for **releasing and upgrading
versioned filesystem skills** ([agentskills.io](https://agentskills.io) style:
a directory with a `SKILL.md` plus `references/`, `scripts/`, and `assets/`)
across the Soliplex projects:

| Repository          | Skills it publishes |
| ------------------- | ------------------- |
| `soliplex`          | `soliplex-docs` |
| `soliplex-template` | `soliplex-template` |
| `soliplex-concierge`| `soliplex-concierge-installer`, `soliplex-concierge-room`, `soliplex-concierge-admin` |

See the **[Skills catalog](overview/skills-catalog.md)** for what each skill
does, where it runs (inside Soliplex or in an external coding agent), its source
repo, and its latest release.

!!! note "Status"
    This site documents the **mechanisms** these projects use and the
    **library API** that provides them. The library is implemented and tested
    (100% branch coverage).

## What it provides

One importable, tested Python package holding the release/upgrade machinery a
versioned filesystem skill needs:

- **`versions`** — `list` / `diff` / `upgrade` a published skill against its
  GitHub releases, driven by a per-skill [`SkillSpec`](reference/api.md).
- **`build`** — assemble a skill into `dist/<name>/`: copy the source tree,
  stamp `SKILL.md` with the source commit, and validate it (with an optional
  `generator` hook for build-time content).
- **`releases`** / **`manifest`** / **`metadata`** / **`_archive`** — GitHub
  release access, the `version.json` schema, reading/stamping `SKILL.md`'s
  `source_commit`, and the download/verify/extract primitives the others build
  on.

## Where to start

=== "I maintain a skill / this library"

    Read the [Overview](overview/concepts.md) for the vocabulary and the
    [release model](overview/release-model.md), then the
    [Mechanisms](mechanisms/building.md) section for how building, publishing,
    and installation map onto the library API. The
    [API reference](reference/api.md) is the full surface.

=== "I have a skill installed and want to manage it"

    Go straight to [Managing an installed skill](mechanisms/versions-cli.md):
    how to **list** published versions, **diff** your installed copy against a
    published one, and **upgrade** (or downgrade) in place.

=== "I want to publish a skill from my own repo"

    Follow [Adopt in a new repo](adoption/quickstart.md): a step-by-step setup
    with copy-paste-ready `skill_versions.py`, `build_skill.py`, and GitHub
    Actions workflow examples.

## How the skills use it

- **Each skill bundles a thin `skill_versions.py`.** Because an installed skill
  runs in an environment where `soliplex_skills` is not installed, it is a small
  [PEP 723](https://peps.python.org/pep-0723/) script that declares
  `# dependencies = ["soliplex-skills>=…"]` in its inline metadata, letting `uv`
  provision the library at run time. It fills in a
  [`SkillSpec`](reference/api.md) and delegates to `SkillVersions`.
- **Build scripts call `soliplex_skills.build`.** `soliplex-template` and
  `soliplex-concierge` build via `build.build_skill` (`discover_skills` plus a
  loop for the multi-skill concierge repo); the `soliplex-docs` builder passes a
  `generator` hook to `build_skill` for its nav-derived documentation map. All
  reuse `metadata.stamp_source_commit` and in-process `skills_ref` validation.
- **Publishing lives in each repo's GitHub Actions workflow** — dual-mode
  releases, the `version.json` manifest, and prune-to-`KEEP_ROLLING` — and the
  build step it runs is the part that calls this library.
