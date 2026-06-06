"""Tests for :mod:`soliplex_skills._archive` (offline)."""

from __future__ import annotations

import hashlib

import pytest

from soliplex_skills import _archive


def test_sha256_matches_hashlib(tmp_path):
    blob = tmp_path / "blob.bin"
    blob.write_bytes(b"some content")

    digest = _archive.sha256(blob)

    assert digest == hashlib.sha256(b"some content").hexdigest()


def test_download_and_extract_then_find_root(
    tmp_path, make_skill, make_tarball
):
    skill = make_skill("demo-skill", files={"scripts/tool.py": "x = 1\n"})
    tarball = make_tarball(skill, tmp_path / "demo.tar.gz")
    dest = tmp_path / "dl"
    dest.mkdir()

    extract_dir = _archive.download_and_extract(tarball.as_uri(), dest)

    root = _archive.find_skill_root(extract_dir)
    assert (root / "SKILL.md").is_file()
    assert (root / "scripts" / "tool.py").read_text() == "x = 1\n"


def test_download_and_extract_verifies_sha256(
    tmp_path, make_skill, make_tarball
):
    skill = make_skill("demo-skill")
    tarball = make_tarball(skill, tmp_path / "demo.tar.gz")
    good = _archive.sha256(tarball)
    dest = tmp_path / "dl"
    dest.mkdir()

    extract_dir = _archive.download_and_extract(
        tarball.as_uri(), dest, expected_sha256=good
    )

    assert _archive.find_skill_root(extract_dir).name == "demo-skill"


def test_download_and_extract_checksum_mismatch(
    tmp_path, make_skill, make_tarball
):
    skill = make_skill("demo-skill")
    tarball = make_tarball(skill, tmp_path / "demo.tar.gz")
    dest = tmp_path / "dl"
    dest.mkdir()

    with pytest.raises(_archive.ChecksumMismatch):
        _archive.download_and_extract(
            tarball.as_uri(), dest, expected_sha256="0" * 64
        )


def test_find_skill_root_without_skill_md(tmp_path):
    extract_dir = tmp_path / "extract"
    (extract_dir / "demo").mkdir(parents=True)

    with pytest.raises(_archive.NoSkillFound):
        _archive.find_skill_root(extract_dir)


def test_install_over_prunes_upstream_deletions(tmp_path, make_skill):
    installed = make_skill(
        "demo-skill",
        files={"references/old.md": "stale\n"},
        parent=tmp_path / "installed",
    )
    upstream = make_skill(
        "demo-skill",
        commit="def5678",
        files={"references/new.md": "fresh\n"},
        parent=tmp_path / "upstream",
    )

    _archive.install_over(upstream, installed)

    assert not (installed / "references" / "old.md").exists()
    assert (installed / "references" / "new.md").read_text() == "fresh\n"


def test_temp_dest_is_removed_on_exit():
    with _archive.temp_dest() as path:
        marker = path / "f.txt"
        marker.write_text("x", encoding="utf-8")
        assert marker.exists()

    assert not path.exists()
