# `soliplex-skills`: skill release / upgrade utilities

This project hosts shared infrastructure for releasing tagge / rolling
versions of filesystem-based (https://agentskills.io) skills from other
Soliplex projects:

- `soliplex`: `soliplex-docs` skill
- `soliplex-template`: `soliplex-template` skill
- `soliplex-concierge`: `soliplex-concierge-installer`,
  `soliplex-concierge.room`, and `soliplex-concierge.admin` skills.

📖 **Full documentation:** <https://soliplex.github.io/soliplex-skills/>

## Features

- Rolling releases of skills as artifacts of Github auto-generated
  repository releases.

- Tagged releases of skills as artifacts of explicitly-managed Github
  releases.

- Embedded `skill_versions.py` script within such skills can query
  available releases, and upgrade / downgrade themselves to a user-selected
  release.

- Support for installation of such skills into Soliiplex installations
  and rooms.
