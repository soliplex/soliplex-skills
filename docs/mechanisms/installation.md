# Installing a published skill

Where [managing an installed skill](versions-cli.md) upgrades a copy that is
*already* on disk, this mechanism covers the **first-time install**: resolving
a published skill to an asset, downloading and verifying it, and extracting its
skill root.

On top of that low-level fetch it offers **installing a skill into a Soliplex
stack**: idempotently placing it under a destination directory (add / upgrade /
no-op), and optionally *defanging* it — stripping the bundled self-management
helper — so the copy is safe to run inside a room agent. The source can be a
freshly downloaded release **or** a local directory (an offline / development
copy), and download is a separate step from install — so a caller can fetch
several skills up front and only install them once every download has
succeeded.

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
4. **Extract** it in a scratch directory and **place** the skill cleanly at
   `<dest>/<name>/` (the returned path). A non-empty target is left untouched
   and `DestinationNotEmpty` is raised unless `force=True`; the check runs
   before any network access, so a refused download touches nothing.

## Installing into a stack

The core is **`install_skill_from`**, which places an already-extracted skill tree
(`source_root`, a directory holding `SKILL.md`) under `<dest>/<name>/`,
idempotently. It first **validates** the source against the agent-skills spec
(raising `SourceInvalid` otherwise); the validator requires the directory name
to equal the skill's `name:`, so the install always lands under the skill's own
name and cannot produce a spec-invalid directory:

1. **Short-circuit if current.** If a copy already exists and its `SKILL.md`
   `source_commit` matches the source's, it is a **no-op** (`UNCHANGED`) unless
   `force=True`.
2. **Install over** any existing copy in place (directories removed first, so
   files deleted upstream do not linger), or copy it in fresh.
3. **Defang** (optional) the *installed copy* — never `source_root`, so a local
   source directory is left byte-for-byte intact (see below).

`source_root` may be a release extracted by `download_skill` or a local working
copy, so `install_skill_from` is the offline / development install path directly.

**`install_skill`** is the convenience wrapper for a published skill: it
downloads + extracts into a temp directory and hands that root to
`install_skill_from`. Splitting the two means a caller can `download_skill` several
skills up front and only `install_skill_from` them once every download has succeeded
(no half-installed stack on a late download failure).

Both return `(skill_root, status)`, where `status` is an **`InstallStatus`**:
`ADDED` (no copy was there), `UPGRADED` (replaced an existing copy), or
`UNCHANGED` (no-op).

`dry_run=True` reports the plan — the `status` that *would* result — and writes
nothing. For `install_skill_from` it is fully offline and exact (it compares the local
commits). For `install_skill` it **does not download the asset**: it resolves
the target commit from the `…-latest` pointer (a small manifest) for an exact
status, but an explicit tag carries no pointer, so a present skill is reported
`UPGRADED` (it cannot prove `UNCHANGED` without the asset) — use
`install_skill_from(…, dry_run=True)` for an exact, fully offline preview.

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

# Low-level: resolve → download → verify → extract to <dest>/<name>/.
root = install.download_skill(docs, version=None, dest=staging)

# High-level: install into a stack at <dest>/soliplex-docs/, defanged.
root, status = install.install_skill(
    docs, version=None, dest=skills_dir, installed_by="my-installer"
)

# Offline / dev: install from a local skill directory (source left intact).
root, status = install.install_skill_from(
    local_dir, dest=skills_dir, installed_by="my-installer"
)
```

- **`PublishedSkill`** — the spec, with a `download_base` property for the
  repo's release-download URLs.
- **`download_skill(spec, version, dest, *, force=False)`** — resolve →
  download → verify → extract; places the skill cleanly at `<dest>/<name>/` and
  returns it. Raises `DestinationNotEmpty` on a non-empty target unless `force`.
- **`install_skill_from(source_root, dest, *, installed_by, defang=True,
  force=False, dry_run=False)`** — install an already-extracted / local skill
  tree into `<dest>/<name>/`. The source is validated (`SourceInvalid` on
  failure) and installed under its own `name:`; it is never modified. Returns
  `(skill_root, InstallStatus)`.
- **`install_skill(spec, version, dest, *, installed_by, defang=True,
  force=False, dry_run=False)`** — download a published skill and hand it to
  `install_skill_from`. `dry_run` reports the plan without fetching the asset. Note
  `defang` **defaults to `True`** here (the `install` CLI command defaults it
  off — see below).
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

# Install from a local copy (offline / dev) instead of downloading:
soliplex-skills install --source-dir ./soliplex-docs --dest skills --defang
```

Unlike the [`install_skill` API](#api), the CLI's **`--defang` defaults to
off** — pass it explicitly to strip the helper. `--installed-by` (default
`soliplex-skills`) is only used by the defang note. `--force` reinstalls even
when the commit matches; `--dry-run` reports the plan without writing.
`--source-dir` installs an already-extracted local copy instead of downloading;
it is validated against the agent-skills spec (and installed under its own
name) and is mutually exclusive with the published-skill selectors (`--skill` /
`--project` / `--pyproject`).

## The `download` CLI command

`download` fetches a published skill and extracts it to `<dest>/<name>/` —
verified against the manifest, but **not** defanged (the raw published
artifact). A non-empty target directory is left untouched unless `--force` is
given. It pairs with `install --source-dir` to separate the network step from
the stack edit:

```console
# Fetch every skill first; install only if all downloads succeed:
soliplex-skills download --skill soliplex-docs --dest staging
soliplex-skills download --skill soliplex-concierge-room --dest staging
soliplex-skills install --source-dir staging/soliplex-docs --dest skills --defang
soliplex-skills install --source-dir staging/soliplex-concierge-room \
    --dest skills --defang
```

!!! note "Out of scope (for now)"
    Even `install_skill` only *places and defangs* a skill — it does not
    **wire** it into a target Soliplex stack by editing `pyproject.toml`,
    `installation.yaml`, and room configs, as the `soliplex-concierge`
    installer does. That stack-editing logic is **intentionally left out** of
    this library; it belongs in a later, installer-specific module built on top
    of these primitives.
