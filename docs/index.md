# Soliplex Skills

`soliplex-skills` is shared infrastructure for **releasing and upgrading
versioned filesystem skills** ([agentskills.io](https://agentskills.io) style:
a directory with a `SKILL.md` plus `references/`, `scripts/`, and `assets/`)
across the Soliplex projects:

| Repository          | Skills it publishes |
| ------------------- | ------------------- |
| `soliplex`          | `soliplex-docs` |
| `soliplex-template` | `soliplex-template` |
| `soliplex-concierge`| `soliplex-concierge-installer`, `soliplex-concierge.room`, `soliplex-concierge.admin` |

!!! warning "Status: design overview"
    This site documents the **mechanisms** these projects already use and the
    **proposed library API** that will absorb them. The library itself is a
    skeleton today — its modules carry typed signatures and behavior
    docstrings, but their bodies raise `NotImplementedError`. Pages that
    describe code are marked accordingly.

## The problem: one mechanism, copied many times

The release/upgrade machinery works well, but it lives as **duplicated source**
in every project:

- **`skill_versions.py`** — a ~575-line, standard-library-only script is
  *vendored verbatim* into every skill's `scripts/` directory (five-plus
  near-identical copies). Only a handful of constants differ
  (`OWNER`/`REPO`/`ASSET_TARBALL`/`POINTER_TAG` and a rolling-tag regex).
  `soliplex-concierge` already marks these copies for coverage-omit with a
  note that the logic is *"slated to move to the shared `soliplex-skills`
  library."*
- **`stamp_source_commit()`** — an identical frontmatter-mutation function is
  copied into both `soliplex-template/scripts/build_skill.py` and
  `soliplex-concierge/scripts/build_skills.py`.
- **GitHub Actions release workflows** — three `build-*skill*.yaml` workflows
  repeat the same dual-mode publishing logic (rolling builds + a `…-latest`
  pointer, or snapshots attached to a release tag), `version.json` manifest
  generation, and prune-to-`KEEP_ROLLING` housekeeping.

`soliplex-skills` exists to hold that logic **once**, as an importable,
testable Python package — so the vendored `skill_versions.py` collapses to a
thin shim and the build scripts and workflows call into a shared library.

## Where to start

=== "I maintain a skill / this library"

    Read the [Overview](overview/concepts.md) for the vocabulary and the
    [release model](overview/release-model.md), then the
    [Mechanisms](mechanisms/building.md) section for how building, publishing,
    and installation map onto the proposed API. The
    [API reference](reference/api.md) is the consolidated contract.

=== "I have a skill installed and want to manage it"

    Go straight to [Managing an installed skill](mechanisms/versions-cli.md):
    how to **list** published versions, **diff** your installed copy against a
    published one, and **upgrade** (or downgrade) in place.
