# API reference

!!! warning "Proposed / not yet implemented"
    This is the **design contract** for the library, not a record of working
    code. The modules under `src/soliplex_skills/` carry these typed signatures
    and behavior docstrings, but their bodies raise `NotImplementedError`. The
    [smoke test](https://github.com/soliplex/soliplex-skills) asserts exactly
    that, so the surface stays honest until each stub is filled in.

There is no re-exporting package `__init__` — **client code imports the
submodule and uses its members by dotted name** (e.g. `from soliplex_skills
import versions` then `versions.SkillVersions(...)`). The headline types are:

| Name | Module | Kind | Purpose |
| --- | --- | --- | --- |
| `ReleaseManifest` | `manifest` | dataclass | `version.json` / `latest.json` schema |
| `SkillSpec` | `versions` | dataclass | the per-skill constants that distinguish one published skill from another |
| `SkillVersions` | `versions` | class | `list` / `diff` / `upgrade` over a published skill |
| `PublishedSkill` | `install` | dataclass | a skill published as a release tarball (first-time install) |

## `manifest` — release manifest schema

| Member | Purpose |
| --- | --- |
| `ReleaseManifest(tag, source_commit, generated, sha256, asset_url)` | the manifest carried by every published build |
| `ReleaseManifest.from_json(raw)` | parse from JSON text/bytes or a mapping |
| `ReleaseManifest.to_json(*, indent=None)` | serialize to the workflow's canonical JSON |

## `metadata` — `SKILL.md` frontmatter identity

| Member | Purpose |
| --- | --- |
| `read_source_commit(skill_md)` | the 7-char `source_commit` recorded in a SKILL.md, or `None` |
| `stamp_source_commit(skill_md, commit)` | idempotently record `metadata.source_commit` |

## `releases` — GitHub releases access

| Member | Purpose |
| --- | --- |
| `list_releases(owner, repo, *, token=None)` | paginate the repo's releases |
| `classify(release, *, rolling_re)` | `(kind, commit)` — rolling vs. release |
| `read_pointer(asset_url)` | resolve a `…-latest` manifest, or `None` |
| `fetch(url, *, accept=…)` | scheme-guarded GitHub fetch with auth header |
| `token()` | `GITHUB_TOKEN` / `GH_TOKEN` from the environment |
| `GitHubAPIError`, `UnsupportedURLScheme` | error types |

## `versions` — list / diff / upgrade

| Member | Purpose |
| --- | --- |
| `SkillSpec(owner, repo, skill_name, asset_tarball, pointer_tag, rolling_re, compare_scope="tree", pointer_manifest="latest.json")` | per-skill configuration |
| `SkillVersions(spec).list(*, kind=None)` | published versions, newest first |
| `SkillVersions(spec).diff(installed_path, target="latest", *, name_only=False)` | installed vs. published |
| `SkillVersions(spec).upgrade(installed_path, target="latest", *, force=False, dry_run=False)` | install a version in place |
| `CompareScope` | `"tree"` (whole skill) or `"references"` (docs only) |

## `build` — assemble / stamp / validate

| Member | Purpose |
| --- | --- |
| `discover_skills(skills_dir)` | names of skill dirs (those with a `SKILL.md`) |
| `git_head_commit(repo_dir)` | the repo's current commit SHA, or `None` |
| `build_skill(name, *, src, dist, commit=None, validate=True)` | build one skill into `dist/<name>/` |

## `install` — first-time install

| Member | Purpose |
| --- | --- |
| `PublishedSkill(name, owner, repo, asset_tarball, pointer_tag, pointer_manifest="latest.json")` | a release-published skill spec |
| `PublishedSkill.download_base` | base URL for the repo's release-download assets |
| `download_skill(spec, version, dest)` | resolve → download → verify → extract; returns the skill root |

## `cli` — console entry point

| Member | Purpose |
| --- | --- |
| `main(argv=None)` | dispatch `list` / `diff` / `upgrade` / `build`; returns an exit code. Installed as the `soliplex-skills` console script. |
