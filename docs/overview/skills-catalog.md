# Skills catalog

`soliplex-skills` releases and upgrades the filesystem skills listed here. They
differ in **where they run**:

- **Inside Soliplex** — installed into a Soliplex room and invoked by that
  room's agent.
- **In an external coding agent** — dropped into an agent like Claude Code,
  acting on a Soliplex deployment from the outside.
- **Both** — equally at home in either place.

Every skill follows the same
[release model](release-model.md): rolling builds plus tagged releases, fronted
by a [`…-latest` pointer](concepts.md#the-latest-pointer-and-latestjson). The
*Latest* link below resolves to that pointer release on GitHub.

## At a glance

| Skill | Runs | Published from | Versioning | Latest |
| --- | --- | --- | --- | --- |
| [`soliplex-docs`](#soliplex-docs) | Both | [`soliplex/soliplex`](https://github.com/soliplex/soliplex) | [repo-coupled](concepts.md#repo-coupled-vs-independently-versioned-skills) | [`docs-latest`](https://github.com/soliplex/soliplex/releases/tag/docs-latest) |
| [`soliplex-template`](#soliplex-template) | External agent | [`soliplex/soliplex-template`](https://github.com/soliplex/soliplex-template) | [independent](concepts.md#repo-coupled-vs-independently-versioned-skills) | [`template-skill-latest`](https://github.com/soliplex/soliplex-template/releases/tag/template-skill-latest) |
| [`soliplex-concierge-installer`](#soliplex-concierge-installer) | External agent | [`soliplex/soliplex-concierge`](https://github.com/soliplex/soliplex-concierge) | [independent](concepts.md#repo-coupled-vs-independently-versioned-skills) | [`installer-skill-latest`](https://github.com/soliplex/soliplex-concierge/releases/tag/installer-skill-latest) |
| [`soliplex-concierge-room`](#soliplex-concierge-room) | Inside Soliplex | [`soliplex/soliplex-concierge`](https://github.com/soliplex/soliplex-concierge) | [independent](concepts.md#repo-coupled-vs-independently-versioned-skills) | [`room-skill-latest`](https://github.com/soliplex/soliplex-concierge/releases/tag/room-skill-latest) |
| [`soliplex-concierge-admin`](#soliplex-concierge-admin) | External agent | [`soliplex/soliplex-concierge`](https://github.com/soliplex/soliplex-concierge) | [independent](concepts.md#repo-coupled-vs-independently-versioned-skills) | [`admin-skill-latest`](https://github.com/soliplex/soliplex-concierge/releases/tag/admin-skill-latest) |

Each skill bundles a `scripts/skill_versions.py` shim, so you can
[list, diff, and upgrade](../mechanisms/versions-cli.md) an installed copy
against what is published.

## Inside Soliplex

### soliplex-concierge-room

Formats a Soliplex room request — a new room, or access to an existing private
one — into a ready-to-file tracking-issue draft (title plus Markdown body). It
does not file anything itself: the calling room agent files the draft with the
`create_gitea_issue` tool. It runs *inside* the `about-<project>` room that the
[installer](#soliplex-concierge-installer) sets up.

- **Source:** [`soliplex/soliplex-concierge`](https://github.com/soliplex/soliplex-concierge)
- **Versioning:** [independently-versioned](concepts.md#repo-coupled-vs-independently-versioned-skills) (`room-skill-vX.Y.Z`)
- **Latest:** [`room-skill-latest`](https://github.com/soliplex/soliplex-concierge/releases/tag/room-skill-latest)

## In an external coding agent

### soliplex-template

Generates a new, runnable Soliplex Docker Compose stack from an embedded
template, or inspects and changes an existing one — querying its resolved
installation config and creating or updating extra RAG databases (with guidance
for wiring them into rooms).

- **Source:** [`soliplex/soliplex-template`](https://github.com/soliplex/soliplex-template)
- **Versioning:** [independently-versioned](concepts.md#repo-coupled-vs-independently-versioned-skills) (`template-skill-vX.Y.Z`)
- **Latest:** [`template-skill-latest`](https://github.com/soliplex/soliplex-template/releases/tag/template-skill-latest)

### soliplex-concierge-installer

Wires the `soliplex-concierge` extension into a target Soliplex stack by running
its bundled `scripts/apply.py` (via `uv run`, no install needed): it creates the
`about-<project>` room — hosting the `create_gitea_issue` tool and the
[room skill](#soliplex-concierge-room) — and merges the required
`installation.yaml` entries.

- **Source:** [`soliplex/soliplex-concierge`](https://github.com/soliplex/soliplex-concierge)
- **Versioning:** [independently-versioned](concepts.md#repo-coupled-vs-independently-versioned-skills) (`installer-skill-vX.Y.Z`)
- **Latest:** [`installer-skill-latest`](https://github.com/soliplex/soliplex-concierge/releases/tag/installer-skill-latest)

### soliplex-concierge-admin

Acts on the room-request issues that the [room skill](#soliplex-concierge-room)
files: lists and reads the open Gitea issues, performs the requested operation
(create a new room, or grant access to a private one), then comments the outcome
and closes the issue. Meant for an administrator triaging pending requests from
an external coding agent.

- **Source:** [`soliplex/soliplex-concierge`](https://github.com/soliplex/soliplex-concierge)
- **Versioning:** [independently-versioned](concepts.md#repo-coupled-vs-independently-versioned-skills) (`admin-skill-vX.Y.Z`)
- **Latest:** [`admin-skill-latest`](https://github.com/soliplex/soliplex-concierge/releases/tag/admin-skill-latest)

## Serves both

### soliplex-docs

A point-in-time snapshot of the full Soliplex documentation — installation,
configuration, operation, and troubleshooting. An agent scans the bundled
documentation map, reads the matching files under `references/`, and answers
strictly from them. Equally useful to an external coding agent and to in-product
help inside Soliplex.

- **Source:** [`soliplex/soliplex`](https://github.com/soliplex/soliplex)
- **Versioning:** [repo-coupled](concepts.md#repo-coupled-vs-independently-versioned-skills) — its tagged releases ride the `soliplex` repo's own `v…` tags
- **Latest:** [`docs-latest`](https://github.com/soliplex/soliplex/releases/tag/docs-latest)
