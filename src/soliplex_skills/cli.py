"""Console entry point: ``soliplex-skills <command>``.

Dispatches the subcommands that the per-skill ``skill_versions.py`` and build
scripts expose today, but driven by the consolidated library:

* ``list``    -- published versions of a skill (see :mod:`.versions`)
* ``diff``    -- installed skill vs. a published version
* ``upgrade`` -- install a published version in place
* ``build``   -- assemble/stamp/validate a skill into ``dist/``
  (see :mod:`.build`)

.. note::

   **Proposed API / not yet implemented.** :func:`main` raises
   :class:`NotImplementedError`.
"""

from __future__ import annotations

from collections import abc


def main(argv: abc.Sequence[str] | None = None) -> int:
    """Parse *argv* and dispatch a subcommand; return a process exit code."""
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
