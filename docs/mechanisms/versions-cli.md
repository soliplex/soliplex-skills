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
python scripts/skill_versions.py diff           # vs. latest
python scripts/skill_versions.py diff v0.68     # vs. a specific tag
python scripts/skill_versions.py diff --name-only
```

Pass **two** published tags to compare them against each other instead of your
installed copy (handy for reviewing what changed between builds):

```console
python scripts/skill_versions.py diff v0.67 v0.68
```

The **whole skill tree** is compared — `SKILL.md`, `scripts/`, `assets/`, and
`references/`. The one per-build-volatile value, the `metadata.source_commit`
stamp in `SKILL.md`, is normalized out, so two builds of identical content
compare equal; every other line (including the build-time
`## Documentation map` a docs skill appends) shows up as a meaningful change.

## `upgrade` — install a published version

Downloads a version (default `latest`) and installs it **in place**.

```console
python scripts/skill_versions.py upgrade            # to latest
python scripts/skill_versions.py upgrade v0.68      # to a specific tag
python scripts/skill_versions.py upgrade --dry-run  # show the plan only
python scripts/skill_versions.py upgrade --force    # reinstall same commit
```

- The download's **`sha256` is verified** against the manifest when known.
- Files are replaced in place, **removing directories first**, so files deleted
  upstream do not linger.
- If your installed `source_commit` already matches the target, it is a no-op
  unless you pass `--force`. (Downgrading is just upgrading to an older tag.)

## The `soliplex-skills` CLI

The same three operations are available from the installed console script,
which reads each skill's configuration from a `[tool.soliplex-skills]` stanza
in `pyproject.toml` (see [CLI configuration](#cli-configuration)) so you don't
repeat the constants on the command line:

```console
soliplex-skills list --skill soliplex-docs
soliplex-skills list --skill soliplex-docs --skill-dir path/to/installed
soliplex-skills diff --skill soliplex-docs --skill-dir path/to/installed
soliplex-skills diff --skill soliplex-docs v0.67 v0.68
soliplex-skills upgrade --skill soliplex-docs --skill-dir path/to/installed --dry-run
```

`--skill` is optional when the config defines a single skill; `--pyproject`
overrides the default upward search for `pyproject.toml`. `--skill-dir` is
optional for `list` (it only adds the `installed` marker — the table and the
`latest` marker render without it) and required for `diff`/`upgrade` unless
`diff` is given two tags.

`upgrade` also accepts `--source-dir` to upgrade from an already-extracted local
directory instead of downloading, and refuses a de-novo install (use
[`install`](installation.md#the-install-cli-command) when the skill is not yet
present). Its `--defang` / `--no-defang` controls whether the upgraded copy keeps
the self-management helper; by default it matches the installed skill's current
state. See [installing and upgrading skills](installation.md) for `install` /
`download` and the install-vs-upgrade distinction.

## CLI configuration

Each skill records its [`SkillSpec`](../reference/api.md) once, as an array of
tables. The `rolling_prefix` is expanded into the rolling-tag regex:

```toml
[[tool.soliplex-skills.skill]]
name = "soliplex-docs"
owner = "soliplex"
repo = "soliplex"
asset_tarball = "soliplex-docs-skill.tar.gz"
pointer_tag = "docs-latest"
rolling_prefix = "docs"          # -> ^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$
```

## Library API

The three subcommands are methods on **`SkillVersions`**, configured by a
**`SkillSpec`** that captures exactly the constants that differ between skills:

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
)

sv = versions.SkillVersions(spec)
sv.list()                          # -> [{tag, date, kind, commit, prerelease}, …]
sv.diff(installed_path, "latest")
sv.upgrade(installed_path, "latest", dry_run=True)
```

!!! note "The bundled shim"
    Each skill's `scripts/skill_versions.py` is a thin shim: it fills in a
    `SkillSpec` (the per-skill constants) and delegates to `SkillVersions` —
    see [How the skills use it](../index.md#how-the-skills-use-it).
