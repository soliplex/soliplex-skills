# Installing a published skill

Where [managing an installed skill](versions-cli.md) upgrades a copy that is
*already* on disk, this mechanism covers the **first-time install**: resolving
a published skill to an asset, downloading and verifying it, and extracting its
skill root. It generalizes the `PublishedSkill` dataclass and `download_skill`
helper found in the `soliplex-concierge` installer.

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

# install.download_skill(docs, version=None, dest=…) -> Path to the skill root
```

- **`PublishedSkill`** — the spec, with a `download_base` property for the
  repo's release-download URLs.
- **`download_skill(spec, version, dest)`** — resolve → download → verify →
  extract; returns the extracted skill root.

!!! note "Out of scope (for now)"
    The `soliplex-concierge` installer does more than fetch a skill — it
    *wires* it into a target Soliplex stack by surgically editing
    `pyproject.toml`, `installation.yaml`, and room configs. That
    stack-editing logic is **intentionally left out** of this initial library;
    it belongs in a later, installer-specific module built on top of
    `download_skill`.
