"""Tests for :mod:`soliplex_skills.releases` (offline)."""

from __future__ import annotations

import json
import re

import pytest

from soliplex_skills import manifest
from soliplex_skills import releases

_ROLLING_RE = re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$")


def test_token_prefers_github_token(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "primary")
    monkeypatch.setenv("GH_TOKEN", "fallback")

    result = releases.token()

    assert result == "primary"


def test_token_falls_back_to_gh_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "fallback")

    result = releases.token()

    assert result == "fallback"


def test_token_absent_returns_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    result = releases.token()

    assert result is None


def test_fetch_rejects_unsupported_scheme():
    with pytest.raises(releases.UnsupportedURLScheme):
        releases.fetch("ftp://example.invalid/x")


def test_fetch_reads_file_url(tmp_path):
    payload = tmp_path / "data.bin"
    payload.write_bytes(b"hello-bytes")

    result = releases.fetch(payload.as_uri())

    assert result == b"hello-bytes"


def test_fetch_wraps_missing_file_as_api_error(tmp_path):
    missing = tmp_path / "nope.bin"

    with pytest.raises(releases.GitHubAPIError):
        releases.fetch(missing.as_uri())


def test_list_releases_paginates(monkeypatch):
    pages = {
        1: [{"tag_name": f"r{i}"} for i in range(100)],
        2: [{"tag_name": "last"}],
    }

    def fake_fetch(url, *, accept=None, auth_token=None):
        page = int(url.rsplit("page=", 1)[1])
        return json.dumps(pages.get(page, [])).encode("utf-8")

    monkeypatch.setattr(releases, "fetch", fake_fetch)

    result = releases.list_releases("soliplex", "soliplex")

    assert len(result) == 101
    assert result[-1]["tag_name"] == "last"


def test_classify_rolling_extracts_commit():
    release = {"tag_name": "docs-2026.05.29-cc9a290"}

    kind, commit = releases.classify(release, rolling_re=_ROLLING_RE)

    assert (kind, commit) == ("rolling", "cc9a290")


def test_classify_release_uses_target_commitish():
    release = {"tag_name": "v0.68", "target_commitish": "a1b2c3d4e5f6"}

    kind, commit = releases.classify(release, rolling_re=_ROLLING_RE)

    assert (kind, commit) == ("release", "a1b2c3d")


def test_classify_release_without_hex_target():
    release = {"tag_name": "v0.68", "target_commitish": "main"}

    kind, commit = releases.classify(release, rolling_re=_ROLLING_RE)

    assert (kind, commit) == ("release", "-")


def test_read_pointer_parses_manifest(tmp_path):
    payload = {
        "tag": "docs-2026.05.29-cc9a290",
        "source_commit": "cc9a290",
        "generated": "2026-05-29",
        "sha256": "0" * 64,
        "asset_url": "https://example.invalid/a.tar.gz",
    }
    pointer = tmp_path / "latest.json"
    pointer.write_text(json.dumps(payload), encoding="utf-8")

    result = releases.read_pointer(pointer.as_uri())

    assert result == manifest.ReleaseManifest.from_json(payload)


def test_read_pointer_missing_returns_none(tmp_path):
    missing = tmp_path / "latest.json"

    result = releases.read_pointer(missing.as_uri())

    assert result is None


def test_read_pointer_invalid_json_returns_none(tmp_path):
    pointer = tmp_path / "latest.json"
    pointer.write_text("not json", encoding="utf-8")

    result = releases.read_pointer(pointer.as_uri())

    assert result is None
