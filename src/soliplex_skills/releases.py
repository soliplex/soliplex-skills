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
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import abc
from typing import Literal

from soliplex_skills.manifest import ReleaseManifest

#: A release is either a dated rolling build or an explicit tagged release.
ReleaseKind = Literal["rolling", "release"]

#: URL schemes :func:`fetch` is willing to open.
ALLOWED_SCHEMES = frozenset({"https", "file"})

#: User-Agent sent with every request (GitHub rejects requests without one).
USER_AGENT = "soliplex-skills"

_API = "https://api.github.com"

#: Matches a 7-to-40 char hex commit (a release's ``target_commitish``).
_HEX_RE = re.compile(r"[0-9a-f]{7,40}")


class GitHubAPIError(RuntimeError):
    """A request to GitHub (or a ``file://`` override) failed."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"GitHub request failed ({reason}): {url}")


class UnsupportedURLScheme(ValueError):
    """A URL used a scheme outside :data:`ALLOWED_SCHEMES`."""

    def __init__(self, url: str, scheme: str):
        self.url = url
        self.scheme = scheme
        super().__init__(
            f"refusing to open URL with unsupported scheme {scheme!r}: {url}"
        )


def token() -> str | None:
    """Return ``GITHUB_TOKEN`` or ``GH_TOKEN`` from the environment, if set."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def fetch(
    url: str,
    *,
    accept: str = "application/vnd.github+json",
    auth_token: str | None = None,
) -> bytes:
    """Fetch *url* with the User-Agent/Accept/auth headers GitHub expects.

    Refuses any scheme outside :data:`ALLOWED_SCHEMES` before opening, and
    wraps transport/HTTP errors as :class:`GitHubAPIError`. *auth_token*
    overrides the environment token from :func:`token`.
    """
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme not in ALLOWED_SCHEMES:
        raise UnsupportedURLScheme(url, scheme)
    request = urllib.request.Request(url)
    request.add_header("User-Agent", USER_AGENT)
    request.add_header("Accept", accept)
    resolved = auth_token if auth_token is not None else token()
    if resolved:
        request.add_header("Authorization", f"Bearer {resolved}")
    # The scheme allow-list above bounds this to https/file.
    try:
        with urllib.request.urlopen(request) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise GitHubAPIError(url, f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GitHubAPIError(url, str(exc.reason)) from exc


def list_releases(
    owner: str, repo: str, *, token: str | None = None
) -> list[dict]:
    """Return every release for ``owner/repo``, paginating the API."""
    releases: list[dict] = []
    page = 1
    while True:
        url = f"{_API}/repos/{owner}/{repo}/releases?per_page=100&page={page}"
        batch = json.loads(fetch(url, auth_token=token))
        if not batch:
            break
        releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return releases


def has_asset(release: abc.Mapping[str, object], name: str) -> bool:
    """Return whether *release* carries an asset called *name*."""
    assets = release.get("assets", []) or []
    return any(asset.get("name") == name for asset in assets)


def classify(
    release: abc.Mapping[str, object], *, rolling_re: re.Pattern[str]
) -> tuple[ReleaseKind, str]:
    """Return ``(kind, commit)`` for a release.

    A tag matching *rolling_re* (a compiled pattern such as
    ``^docs-\\d{4}\\.\\d{2}\\.\\d{2}-[0-9a-f]+$``) is a ``"rolling"`` build and
    its commit is the trailing ``-<sha>`` segment; anything else is a
    ``"release"`` whose commit is derived from ``target_commitish``.
    """
    tag = release.get("tag_name") or release.get("tagName") or ""
    if rolling_re.match(tag):
        return "rolling", tag.rsplit("-", 1)[1]
    target = str(release.get("target_commitish", ""))
    commit = target[:7] if _HEX_RE.fullmatch(target) else "-"
    return "release", commit


def read_pointer(asset_url: str) -> ReleaseManifest | None:
    """Resolve a ``…-latest`` pointer manifest, or ``None`` if unavailable.

    *asset_url* is the URL of the pointer tag's ``latest.json`` asset. Returns
    ``None`` (rather than raising) when the pointer cannot be read or parsed,
    so callers can fall back to listing releases.
    """
    try:
        raw = fetch(asset_url, accept="application/octet-stream")
    except GitHubAPIError:
        return None
    try:
        return ReleaseManifest.from_json(raw)
    except (json.JSONDecodeError, KeyError):
        return None
