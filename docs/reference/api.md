# API reference

!!! note "Implemented"
    This is the library's public surface. Every member below is implemented
    and covered by the test suite (100% branch coverage); the modules under
    `src/soliplex_skills/` are the source of truth.

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
| `read_source_commit(skill_md)` | the 7-char `source_commit` recorded in a SKILL.md, or `None` (parsed via `skills_ref`) |
| `stamp_metadata(skill_md, *, version=None, source_commit=None, generated=None)` | idempotently record the build-identity `metadata` entries |

## `releases` — GitHub releases access

| Member | Purpose |
| --- | --- |
| `list_releases(owner, repo, *, token=None)` | paginate the repo's releases |
| `classify(release, *, rolling_re)` | `(kind, commit)` — rolling vs. release |
| `has_asset(release, name)` | whether a release carries an asset called `name` |
| `read_pointer(asset_url)` | resolve a `…-latest` manifest, or `None` |
| `fetch(url, *, accept=…, auth_token=None)` | scheme-guarded GitHub fetch (`https`/`file`) |
| `token()` | `GITHUB_TOKEN` / `GH_TOKEN` from the environment |
| `GitHubAPIError`, `UnsupportedURLScheme` | error types |

## `versions` — list / diff / upgrade

| Member | Purpose |
| --- | --- |
| `SkillSpec(owner, repo, skill_name, asset_tarball, pointer_tag, rolling_re, pointer_manifest="latest.json")` | per-skill configuration |
| `SkillVersions(spec).list(*, kind=None, installed_path=None, mark_latest=False)` | published versions, newest first; flags the installed / latest rows |
| `SkillVersions(spec).diff(installed_path, target="latest", *, name_only=False)` | installed vs. published (whole tree; the `source_commit` stamp is ignored) |
| `SkillVersions(spec).diff_published(left, right, *, name_only=False)` | two published versions vs. each other |
| `SkillVersions(spec).upgrade(installed_path, target="latest", *, force=False, dry_run=False)` | install a version in place |
| `format_list_table(rows)` | render `list` rows as the aligned, marked table |

!!! note "Deprecated"
    `SkillSpec` still accepts a `compare_scope=` argument for backward
    compatibility, but it is ignored (and warns): `diff` always compares the
    whole skill tree, normalizing out the per-build `source_commit` stamp.

## `build` — assemble / stamp / validate

| Member | Purpose |
| --- | --- |
| `discover_skills(skills_dir)` | names of skill dirs (those with a `SKILL.md`) |
| `git_head_commit(repo_dir)` | the repo's current commit SHA, or `None` |
| `build_skill(name, *, src, dist, commit=None, validate=True, generator=None)` | build one skill into `dist/<name>/`; optional `generator(out_dir)` runs between stamp and validate |

## `install` — install / upgrade a skill

`install` and `upgrade` are distinct **policy** operations over a shared
mechanical core: `install` is for putting a skill in place (it refuses to change
an already-installed version); `upgrade` is for changing the version of one
that is already there (it refuses a de-novo install). Each has a published
variant (downloads) and a local `…_from` variant (an already-extracted dir).

| Member | Purpose |
| --- | --- |
| `PublishedSkill(name, owner, repo, asset_tarball, pointer_tag, pointer_manifest="latest.json")` | a release-published skill spec |
| `PublishedSkill.download_base` | base URL for the repo's release-download assets |
| `PublishedSkill.asset_url(tag)` / `.pointer_url()` | asset / pointer-manifest URLs |
| `download_skill(spec, version, dest, *, force=False)` | resolve → download → verify → extract; places the skill cleanly at `<dest>/<name>/` (raises `exceptions.DestinationNotEmpty` on a non-empty target unless `force`) |
| `install_skill(spec, version, dest, *, installed_by, defang=True, force=False, dry_run=False)` | **install-only** published: refuses a different installed version (raising `exceptions.VersionMismatch`); `dry_run` skips the asset download for `latest` (downloads an explicit tag to classify) |
| `install_skill_from(source_root, dest, *, installed_by, defang=True, force=False, dry_run=False)` | **install-only** from a local / already-extracted dir; validates the source (installed under its own name) and never modifies it |
| `upgrade_skill(spec, version, dest, *, installed_by, defang=True, force=False, dry_run=False)` | **upgrade-only** published: refuses a de-novo install (raising `exceptions.NotInstalled`); otherwise as `install_skill` |
| `upgrade_skill_from(source_root, dest, *, installed_by, defang=True, force=False, dry_run=False)` | **upgrade-only** from a local dir |
| `defang_skill(skill_dir, *, installed_by, note=None)` | strip the self-management helper so the copy is safe inside a room agent |
| `is_defanged(skill_dir)` | whether a copy has been defanged (its `skill_versions.py` removed) — lets `upgrade` preserve a skill's defang state |
| `InstallStatus` | `ADDED` / `UNCHANGED` / `REINSTALLED` (same commit, forced) / `UPGRADED` (different commit) |

## `exceptions` — shared error types

Exceptions raised from the library modules.

| Member | Purpose |
| --- | --- |
| `PointerUnavailable` | skill has unresolvable `…-latest` pointer manifest  |
| `DestinationNotEmpty` | `download_skill` target directory is non-empty |
| `SourceInvalid` | a source dir failed agent-skills validation |
| `VersionMismatch` | `install` refused: a *different* version is installed |
| `NotInstalled` | `upgrade` refused: nothing is installed |

## `config` — load specs from `pyproject.toml`

| Member | Purpose |
| --- | --- |
| `load_skill_specs(pyproject_path)` | `{name: SkillSpec}` from `[[tool.soliplex-skills.skill]]` |
| `find_pyproject(start=None)` | nearest `pyproject.toml` at/above `start` (cwd default) |
| `SkillConfigError` (+ subclasses) | raised on missing/invalid configuration |

## `cli` — console entry point

| Member | Purpose |
| --- | --- |
| `main(argv=None)` | dispatch `list` / `diff` / `upgrade` / `install` / `download` / `build`; returns an exit code. Installed as the `soliplex-skills` console script. `install` (de-novo, refuses a different version) and `upgrade` (refuses a de-novo install) both accept `--source-dir` for a local source; `download` fetches a published skill to a local directory. |
