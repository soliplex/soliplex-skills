"""Query a repository's GitHub releases and classify skill-bearing ones.

This is the GitHub-facing half of the version-management logic vendored in
every ``skill_versions.py``: paginate the releases API, keep the releases that
actually carry a skill's asset tarball, and classify each as a *rolling* build
or a *tagged* release. It also resolves a skill's ``…-latest`` pointer to a
:class:`~soliplex_skills.manifest.ReleaseManifest`.

Network access to ``api.github.com`` / ``github.com`` is required. A token in
``GITHUB_TOKEN`` or ``GH_TOKEN`` raises the API rate limit. Only ``https`` and
``file`` URL schemes are honored (the ``file`` scheme supports the
``--asset-url`` testing override).

.. note::

   **Proposed API / not yet implemented.** Function bodies raise
   :class:`NotImplementedError`.
"""

from __future__ import annotations

from collections import abc
from typing import Literal

from soliplex_skills.manifest import ReleaseManifest

#: A release is either a dated rolling build or an explicit tagged release.
ReleaseKind = Literal["rolling", "release"]

#: URL schemes :func:`fetch` is willing to open.
ALLOWED_SCHEMES = frozenset({"https", "file"})


class GitHubAPIError(RuntimeError):
    """A request to GitHub (or a ``file://`` override) failed."""


class UnsupportedURLScheme(ValueError):
    """A URL used a scheme outside :data:`ALLOWED_SCHEMES`."""


def token() -> str | None:
    """Return ``GITHUB_TOKEN`` or ``GH_TOKEN`` from the environment, if set."""
    raise NotImplementedError


def fetch(url: str, *, accept: str = "application/vnd.github+json") -> bytes:
    """Fetch *url* with the User-Agent/Accept/auth headers GitHub expects.

    Refuses any scheme outside :data:`ALLOWED_SCHEMES` before opening, and
    wraps transport/HTTP errors as :class:`GitHubAPIError`.
    """
    raise NotImplementedError


def list_releases(owner: str, repo: str, *, token: str | None = None) -> list[dict]:
    """Return every release for ``owner/repo``, paginating the GitHub API."""
    raise NotImplementedError


def classify(release: abc.Mapping[str, object], *, rolling_re) -> tuple[ReleaseKind, str]:
    """Return ``(kind, commit)`` for a release.

    A tag matching *rolling_re* (a compiled pattern such as
    ``^docs-\\d{4}\\.\\d{2}\\.\\d{2}-[0-9a-f]+$``) is a ``"rolling"`` build and
    its commit is the trailing ``-<sha>`` segment; anything else is a
    ``"release"`` whose commit is derived from ``target_commitish``.
    """
    raise NotImplementedError


def read_pointer(asset_url: str) -> ReleaseManifest | None:
    """Resolve a ``…-latest`` pointer manifest, or ``None`` if unavailable.

    *asset_url* is the URL of the pointer tag's ``latest.json`` asset. Returns
    ``None`` (rather than raising) when the pointer cannot be read or parsed,
    so callers can fall back to listing releases.
    """
    raise NotImplementedError
