# Managing an installed skill

Every skill bundles a `scripts/skill_versions.py` helper so you can manage your
installed copy against what has been published — without leaving the skill or
installing anything extra. It offers three subcommands.

!!! note "Network & auth"
    These commands reach `api.github.com` / `github.com`. Set `GITHUB_TOKEN`
    (or `GH_TOKEN`) to raise the API rate limit. Only `https` (and a
    `file://` testing override) URLs are honored.

## `list` — what has been published?

Shows the skill's published versions newest-first — both
[rolling builds](../overview/concepts.md#rolling-build-vs-tagged-release) and
tagged releases — marking your installed copy and the current `latest` pointer.

```console
$ python scripts/skill_versions.py list
TAG                          DATE        KIND     COMMIT
docs-2026.05.29-cc9a290f     2026-05-29  rolling  cc9a290  ← installed, latest
v0.68                        2026-05-20  release  a1b2c3d
docs-2026.05.18-a1b2c3d      2026-05-18  rolling  a1b2c3d
```

Filter with `--kind {rolling,release}`, or get machine-readable output with
`--json`.

## `diff` — how does my copy differ?

Compares your installed skill against a published version (default `latest`).

```console
$ python scripts/skill_versions.py diff           # vs. latest
$ python scripts/skill_versions.py diff v0.68     # vs. a specific tag
$ python scripts/skill_versions.py diff --name-only
```

What gets compared depends on the skill's **compare scope**:

- `references` — only the `references/` Markdown (used by `soliplex-docs`,
  whose payload is documentation);
- `tree` — the whole skill tree: `SKILL.md`, `scripts/`, `assets/`,
  `references/` (used by `soliplex-template` and the concierge skills).

## `upgrade` — install a published version

Downloads a version (default `latest`) and installs it **in place**.

```console
$ python scripts/skill_versions.py upgrade            # to latest
$ python scripts/skill_versions.py upgrade v0.68      # to a specific tag
$ python scripts/skill_versions.py upgrade --dry-run  # show the plan only
$ python scripts/skill_versions.py upgrade --force    # reinstall same commit
```

- The download's **`sha256` is verified** against the manifest when known.
- Files are replaced in place, **removing directories first**, so files deleted
  upstream do not linger.
- If your installed `source_commit` already matches the target, it is a no-op
  unless you pass `--force`. (Downgrading is just upgrading to an older tag.)

## Proposed API

!!! warning "Proposed / not yet implemented"
    The methods below are design stubs (`versions.py`). Their bodies raise
    `NotImplementedError`.

The three subcommands are methods on **`SkillVersions`**, configured by a
**`SkillSpec`** that captures exactly the constants that differ between skills
today:

```python
import re
from soliplex_skills import versions

spec = versions.SkillSpec(
    owner="soliplex",
    repo="soliplex",
    skill_name="soliplex-docs",
    asset_tarball="soliplex-docs-skill.tar.gz",
    pointer_tag="docs-latest",
    rolling_re=re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"),
    compare_scope="references",   # docs compares references/ only
)

sv = versions.SkillVersions(spec)
sv.list()                          # -> [{tag, date, kind, commit, prerelease}, …]
sv.diff(installed_path, "latest")
sv.upgrade(installed_path, "latest", dry_run=True)
```

!!! note "What this de-duplicates"
    The ~575-line `skill_versions.py` is currently vendored verbatim into five
    or more skills, differing only in those `SkillSpec` fields and the
    `compare_scope` toggle. Under this design the vendored script becomes a
    thin shim: it fills in a `SkillSpec` and delegates to `SkillVersions`.
