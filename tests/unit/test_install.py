"""Tests for :mod:`soliplex_skills.install` (offline)."""

from __future__ import annotations

import json

import pytest

from soliplex_skills import _archive
from soliplex_skills import install
from soliplex_skills import releases
from soliplex_skills import versions


def _spec():
    return install.PublishedSkill(
        name="soliplex-docs",
        owner="soliplex",
        repo="soliplex",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
    )


def _serve(mapping):
    def _fetch(url, *, accept=None, auth_token=None):
        for suffix, payload in mapping.items():
            if url.endswith(suffix):
                return payload
        raise releases.GitHubAPIError(url, "not mapped")

    return _fetch


def _publish(make_skill, make_tarball, tmp_path, *, commit, bad_sha=False):
    skill = make_skill(
        "soliplex-docs",
        commit=commit,
        files={"references/a.md": "hi\n"},
        parent=tmp_path / f"pub-{commit}",
    )
    tarball = make_tarball(skill, tmp_path / f"{commit}.tar.gz")
    tag = f"docs-2026.05.29-{commit}"
    manifest = {
        "tag": tag,
        "source_commit": commit,
        "generated": "2026-05-29",
        "sha256": "0" * 64 if bad_sha else _archive.sha256(tarball),
        "asset_url": (
            "https://github.com/soliplex/soliplex/releases/download/"
            f"{tag}/soliplex-docs-skill.tar.gz"
        ),
    }
    return {
        "soliplex-docs-skill.tar.gz": tarball.read_bytes(),
        "latest.json": json.dumps(manifest).encode("utf-8"),
    }


def test_download_base_and_urls():
    spec = _spec()

    base = spec.download_base

    assert base == "https://github.com/soliplex/soliplex/releases/download"
    assert spec.asset_url("v0.68").endswith(
        "/v0.68/soliplex-docs-skill.tar.gz"
    )
    assert spec.pointer_url().endswith("/docs-latest/latest.json")


def test_download_skill_via_pointer(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "dl"
    dest.mkdir()

    root = install.download_skill(_spec(), None, dest)

    assert (root / "SKILL.md").is_file()
    assert root.name == "soliplex-docs"


def test_download_skill_explicit_tag(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "dl"
    dest.mkdir()

    root = install.download_skill(_spec(), "docs-2026.05.29-bbbbbbb", dest)

    assert (root / "references" / "a.md").read_text() == "hi\n"


def test_download_skill_pointer_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(releases, "fetch", _serve({}))
    dest = tmp_path / "dl"
    dest.mkdir()

    with pytest.raises(versions.PointerUnavailable):
        install.download_skill(_spec(), None, dest)


def test_download_skill_checksum_mismatch(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(
        make_skill, make_tarball, tmp_path, commit="bbbbbbb", bad_sha=True
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "dl"
    dest.mkdir()

    with pytest.raises(_archive.ChecksumMismatch):
        install.download_skill(_spec(), None, dest)
