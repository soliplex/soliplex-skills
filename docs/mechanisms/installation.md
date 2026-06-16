# Installing and upgrading skills

This mechanism gets a published skill (or a local copy) onto disk and into a
Soliplex stack. It is built from a few composable pieces — **download**,
**install**, **upgrade**, and **defang** — each a library function (see the
[API reference](../reference/api.md)) and a
`soliplex-skills` subcommand.

Where [managing an installed skill](versions-cli.md) is a skill driving its own
bundled `skill_versions.py` shim, this is the outside-in view: a tool placing
and updating skills in a stack.

## The pieces

- **download** — resolve a skill's release asset (via its `…-latest`
  [pointer manifest](../overview/release-model.md#the-manifest), or an explicit
  tag), verify the `sha256`, extract it, and place the tree cleanly at
  `<dest>/<name>/`. This is the network step, kept separate so a caller can
  fetch several skills up front and only touch the stack once every download has
  succeeded. A non-empty target is refused (`DestinationNotEmpty`) unless
  `force` — checked *before* any network access, so a refused download touches
  nothing.
- **install** — put a skill in place: `ADDED` when the target is fresh,
  `UNCHANGED` (a no-op) or `REINSTALLED` (under `force`, re-laying the identical
  commit to wipe an admin's stray edits) when the **same** version is already
  there, and **refused with `VersionMismatch`** when a **different** version is
  installed — changing versions is `upgrade`'s job.
- **upgrade** — change an installed skill's version: `UPGRADED` for a different
  commit, `UNCHANGED` / `REINSTALLED` for a matching one, and **refused with
  `NotInstalled`** when nothing is installed — a first-time install is
  `install`'s job.
- **defang** — strip the bundled `scripts/skill_versions.py` self-management
  helper so a copy running inside a room agent can't reach upgrade machinery
  (detailed [below](#defanging-a-stack-installed-skill)).

A few properties hold across both install and upgrade:

- **Source** — published release or a local directory. The published functions
  download first; the `…_from` variants take an already-extracted directory (an
  offline / development copy). Either way the source is **validated** against the
  agent-skills spec (`SourceInvalid` otherwise) and installed under its own
  `name:`, so the result is always a spec-valid `<dest>/<name>/`. A local source
  is never modified — defanging acts on the installed copy.
- **Status** — each returns `(skill_root, InstallStatus)`: one of `ADDED`,
  `UNCHANGED`, `REINSTALLED`, `UPGRADED`.
- **Dry-run** — reports the plan and writes nothing. The `…_from` variants are
  exact and fully offline (they compare local commits); the published variants
  skip the asset download when the target commit is knowable from the `latest`
  pointer, fetching only an explicit tag (to an auto-removed temp dir) to
  classify it.

## Defanging a stack-installed skill

A skill bundles a `scripts/skill_versions.py`
[self-management helper](versions-cli.md), but a copy running inside a room
agent cannot safely drive it — the room agent serves requests from non-admin
users. `defang_skill` makes such a copy safe:

- it removes `scripts/skill_versions.py` (and any `scripts/__pycache__`, then
  `scripts/` itself if now empty);
- it rewrites the `SKILL.md` self-management section to a short note. The section
  is located by scanning the `##` headings and finding the one whose body
  mentions `skill_versions.py` (the heading is preserved); if no section matches,
  only the script files are removed and the markdown is left untouched.

The replacement text is built by `format_defang_note(heading, installed_by=…)`;
callers can override it with the `note` argument. This is the counterpart to the
[`## Managing this skill` epilogue](../adoption/quickstart.md#document-the-shim-in-skillmd)
a skill author appends to `SKILL.md` — write that section keeping its `##`
heading and `skill_versions.py` reference, and the installer can find and defang
it.

## From Python

```python
from soliplex_skills import install

docs = install.PublishedSkill(
    name="soliplex-docs",
    owner="soliplex",
    repo="soliplex",
    asset_tarball="soliplex-docs-skill.tar.gz",
    pointer_tag="docs-latest",
)

# Download + place the raw skill tree at staging/soliplex-docs/.
root = install.download_skill(docs, version=None, dest=staging)

# Install the latest published build into the stack, defanged.
root, status = install.install_skill(
    docs, version=None, dest=skills_dir, installed_by="my-installer"
)

# Upgrade an already-installed skill from a local directory.
root, status = install.upgrade_skill_from(
    local_dir, dest=skills_dir, installed_by="my-installer"
)
```

The [API reference](../reference/api.md) lists
every function and signature. Note `defang` **defaults to `True`** in the
library (the CLI defaults it off — see below).

## The `install` CLI command

`install` is available from the console script, reading the skill's
[`[tool.soliplex-skills]` stanza](versions-cli.md#cli-configuration) so the
constants need not be repeated:

```console
# Install latest into ./skills/<name>/ (keeps the helper by default):
soliplex-skills install --skill soliplex-docs --dest skills

# Defang on the way in, recording who installed it, and preview first:
soliplex-skills install --skill soliplex-docs --dest skills --defang \
    --installed-by my-installer --dry-run

# Re-lay the same version in place, wiping stray local edits:
soliplex-skills install --skill soliplex-docs --dest skills --force

# Install from a local copy (offline / dev) instead of downloading:
soliplex-skills install --source-dir ./soliplex-docs --dest skills --defang
```

Two behaviors aren't obvious from `--help`: the CLI's **`--defang` defaults to
off** (the opposite of the [library default](#from-python)), and `install`
**refuses to overwrite a different installed version** — exit 2, pointing at
`upgrade`; `--force` only re-lays the *same* version.

`upgrade` is the counterpart — `soliplex-skills upgrade --skill-dir <installed>
[--source-dir <dir>]` — changing the version and refusing a de-novo install. Its
`--defang` defaults to **matching the installed skill's current state** (pass
`--defang` / `--no-defang` to override). See
[the `upgrade` command](versions-cli.md).

## The `download` CLI command

`download` fetches a published skill and extracts it to `<dest>/<name>/` —
verified against the manifest, but **not** defanged (the raw published artifact).
It pairs with `install --source-dir` to split the network step from the stack
edit, so every skill is in hand before any is installed:

```console
# Fetch every skill first; install only once all downloads succeed:
soliplex-skills download --skill soliplex-docs --dest staging
soliplex-skills download --skill soliplex-concierge-room --dest staging
soliplex-skills install --source-dir staging/soliplex-docs --dest skills --defang
soliplex-skills install --source-dir staging/soliplex-concierge-room \
    --dest skills --defang
```

!!! note "Out of scope (for now)"
    These commands only *place, upgrade, and defang* a skill — they do not
    **wire** it into a Soliplex stack by editing `pyproject.toml`,
    `installation.yaml`, and room configs, as the `soliplex-concierge` installer
    does. That stack-editing logic is **intentionally left out** of this
    library; it belongs in a later, installer-specific layer built on top of
    these primitives.
