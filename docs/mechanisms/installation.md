# Installing a published skill

Where [managing an installed skill](versions-cli.md) upgrades a copy that is
*already* on disk, this mechanism covers the **first-time install**: resolving
a published skill to an asset, downloading and verifying it, and extracting its
skill root.

On top of that low-level fetch it offers **installing a skill into a Soliplex
stack**: idempotently placing it under a destination directory (add / upgrade /
no-op), and optionally *defanging* it — stripping the bundled self-management
helper — so the copy is safe to run inside a room agent.

## Resolving and downloading

A skill is identified by a small spec (owner, repo, asset tarball, pointer
tag). To install it:

1. **Resolve the target.**
   - No explicit version → read the skill's `…-latest`
     [pointer manifest](../overview/release-model.md#the-manifest) and use its
     `asset_url` (and its recorded `sha256`).
   - An explicit tag → build the asset URL by name from the tag.
2. **Download** the tarball.
3. **Verify** its `sha256` against the manifest when one is known.
4. **Extract** and return the skill root — the directory containing `SKILL.md`.

## Installing into a stack

`install_skill` builds on `download_skill` to place a skill under a destination
directory at `<dest>/<skill-name>/`, idempotently:

1. **Extract to a temp dir.** The skill is downloaded and unpacked into a
   temporary directory first, never directly over the live copy.
2. **Short-circuit if current.** If a copy already exists and its
   `SKILL.md` `source_commit` matches the published target, it is a **no-op**
   (`UNCHANGED`) unless `force=True`.
3. **Defang** (optional) the temp copy — see below.
4. **Install over** any existing copy in place (directories removed first, so
   files deleted upstream do not linger), or copy it in fresh.

It returns `(skill_root, status)`, where `status` is an **`InstallStatus`**:
`ADDED` (no copy was there), `UPGRADED` (replaced an existing copy), or
`UNCHANGED` (no-op). `dry_run=True` reports the plan and writes nothing
(returning `UNCHANGED`).

## Defanging a stack-installed skill

A skill bundles a `scripts/skill_versions.py`
[self-management helper](versions-cli.md), but a copy running inside a room
agent cannot usefully drive it — the room agent is not a coding agent and the
copy is updated from the *outside*. `defang_skill` makes such a copy safe:

- it removes `scripts/skill_versions.py` (and any `scripts/__pycache__`,
  then `scripts/` itself if now empty);
- it rewrites the `SKILL.md` self-management section to a short note. The
  section is located by scanning the `##` headings and finding the one whose
  body mentions `skill_versions.py` (the heading is preserved); if no section
  matches, only the script files are removed and the markdown is left untouched.

The replacement text is built by `format_defang_note(heading, installed_by=…)`;
callers can override it with the `note` argument. This is the counterpart to
the [`## Managing this skill` epilogue](../adoption/quickstart.md#document-the-shim-in-skillmd)
a skill author appends to `SKILL.md` — write that section keeping its `##`
heading and `skill_versions.py` reference, and the installer can find and
defang it.

## API

The [`install` module](../reference/api.md):

```python
from soliplex_skills import install

docs = install.PublishedSkill(
    name="soliplex-docs",
    owner="soliplex",
    repo="soliplex",
    asset_tarball="soliplex-docs-skill.tar.gz",
    pointer_tag="docs-latest",
)

# Low-level: resolve → download → verify → extract; returns the skill root.
root = install.download_skill(docs, version=None, dest=tmp)

# High-level: install into a stack at <dest>/soliplex-docs/, defanged.
root, status = install.install_skill(
    docs, version=None, dest=skills_dir, installed_by="my-installer"
)
```

- **`PublishedSkill`** — the spec, with a `download_base` property for the
  repo's release-download URLs.
- **`download_skill(spec, version, dest)`** — resolve → download → verify →
  extract; returns the extracted skill root.
- **`install_skill(spec, version, dest, *, installed_by, defang=True,
  force=False, dry_run=False)`** — install into `<dest>/<name>/`; returns
  `(skill_root, InstallStatus)`. Note `defang` **defaults to `True`** here (the
  `install` CLI command defaults it off — see below).
- **`defang_skill(skill_dir, *, installed_by, note=None)`** — strip the helper
  and rewrite the self-management section in place.
- **`format_defang_note(heading, *, installed_by)`** — render the default
  defang note.
- **`InstallStatus`** — `ADDED` / `UPGRADED` / `UNCHANGED`.

## The `install` CLI command

`install` is also available from the console script, reading the skill's
[`[tool.soliplex-skills]` stanza](versions-cli.md#cli-configuration) so the
constants need not be repeated:

```console
# Install latest into ./skills/<name>/ (keeps the helper by default):
soliplex-skills install --skill soliplex-docs --dest skills

# Defang on the way in, recording who installed it, and preview first:
soliplex-skills install --skill soliplex-docs --dest skills --defang \
    --installed-by my-installer --dry-run

# Reinstall a specific tag even if the installed commit already matches:
soliplex-skills install --skill soliplex-docs --dest skills v0.68 --force
```

Unlike the [`install_skill` API](#api), the CLI's **`--defang` defaults to
off** — pass it explicitly to strip the helper. `--installed-by` (default
`soliplex-skills`) is only used by the defang note. `--force` reinstalls even
when the commit matches; `--dry-run` reports the plan without writing.

!!! note "Out of scope (for now)"
    Even `install_skill` only *places and defangs* a skill — it does not
    **wire** it into a target Soliplex stack by editing `pyproject.toml`,
    `installation.yaml`, and room configs, as the `soliplex-concierge`
    installer does. That stack-editing logic is **intentionally left out** of
    this library; it belongs in a later, installer-specific module built on top
    of these primitives.
