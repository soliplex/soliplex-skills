# Publishing a skill

Publishing turns a [built](building.md) `dist/<name>/` into GitHub release
assets, following the [release model](../overview/release-model.md). It is
driven by a GitHub Actions workflow in the skill's source repository — one
`build-*skill*.yaml` per repo today, all repeating the same logic.

## What the workflow does

For each skill it publishes, the workflow:

1. **Computes build identity** — short SHA, generation date, the rolling tag
   `<prefix>-YYYY.MM.DD-<sha7>`, and the asset `sha256`.
2. **Packages** the `dist/<name>/` tree into a `.tar.gz` and `.zip`.
3. **Emits a manifest** — the `version.json` / `latest.json` payload
   (`{tag, source_commit, generated, sha256, asset_url}`).
4. **Publishes** in the appropriate mode:
   - *rolling* — create the dated prerelease, update the `<prefix>-latest`
     pointer, and prune old rolling builds to `KEEP_ROLLING`;
   - *tagged, repo-coupled* — attach the assets to the repo's `v…` release;
   - *tagged, independently-versioned* — publish under the skill's own
     `<skill>-vX.Y.Z` tag namespace.

## Which tag a tagged release lands on

This is the one decision that varies, and it follows the skill's versioning
(see [the release model](../overview/release-model.md#tagged-releases)):

| Skill versioning | Trigger | Tag the snapshot lands on |
| --- | --- | --- |
| Repo-coupled | repo `release: published` | the repo's own `v…` tag |
| Independently-versioned | the skill's own curated release | `<skill>-vX.Y.Z` (the skill's namespace) |

A **client never has to care** which of the two it is: any non-rolling tag
carrying the skill's asset tarball is simply a "release". The per-skill
`prefix` / `rolling_re` / `pointer_tag` in
[`SkillSpec`](../reference/api.md) already namespace everything per skill, so
independent tagged releases slot in without special handling.

## Library boundary

!!! warning "Proposed / not yet implemented"
    The publishing **orchestration** stays in the workflow YAML — it is where
    GitHub credentials, the releases API, and pruning naturally live. What the
    library factors out are the **reusable primitives** the workflow currently
    open-codes in `bash`/`jq`:

    - the manifest schema and (de)serialization —
      [`manifest.ReleaseManifest`](../reference/api.md);
    - reading the build identity (`source_commit`) back from a built skill —
      [`metadata.read_source_commit`](../reference/api.md);
    - rolling-vs-release tag classification —
      [`releases.classify`](../reference/api.md).

    In short: **the library provides the manifest/identity primitives; the
    workflow orchestrates.** This keeps the workflow thin and ensures the
    publisher and the [client](versions-cli.md) agree on one manifest shape.
