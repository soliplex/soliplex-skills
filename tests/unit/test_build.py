"""Tests for :mod:`soliplex_skills.build` (offline)."""

from __future__ import annotations

import subprocess
from unittest import mock

import pytest

from soliplex_skills import build
from soliplex_skills import metadata


def test_discover_skills_finds_only_skill_dirs(tmp_path, make_skill):
    make_skill("alpha", parent=tmp_path)
    make_skill("beta", parent=tmp_path)
    (tmp_path / "not-a-skill").mkdir()

    result = build.discover_skills(tmp_path)

    assert result == ["alpha", "beta"]


def test_git_head_commit_none_without_git(tmp_path, monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda _name: None)

    result = build.git_head_commit(tmp_path)

    assert result is None


def test_build_skill_copies_and_stamps(tmp_path, make_skill):
    src = tmp_path / "skills"
    make_skill(
        "demo", commit=None, files={"scripts/tool.py": "x = 1\n"}, parent=src
    )
    dist = tmp_path / "dist"

    out = build.build_skill(
        "demo", src=src, dist=dist, commit="abc1234", validate=False
    )

    assert out == dist / "demo"
    assert (out / "scripts" / "tool.py").read_text() == "x = 1\n"
    assert metadata.read_source_commit(out / "SKILL.md") == "abc1234"


def test_build_skill_skips_pycache(tmp_path, make_skill):
    src = tmp_path / "skills"
    make_skill(
        "demo",
        files={"scripts/__pycache__/tool.pyc": "junk\n"},
        parent=src,
    )
    dist = tmp_path / "dist"

    out = build.build_skill("demo", src=src, dist=dist, validate=False)

    assert not (out / "scripts" / "__pycache__").exists()


def test_build_skill_overwrites_existing(tmp_path, make_skill):
    src = tmp_path / "skills"
    make_skill("demo", parent=src)
    dist = tmp_path / "dist"
    stale = dist / "demo" / "stale.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text("old\n", encoding="utf-8")

    out = build.build_skill("demo", src=src, dist=dist, validate=False)

    assert not (out / "stale.txt").exists()


def test_build_skill_missing_source_raises(tmp_path):
    with pytest.raises(build.SkillNotFound):
        build.build_skill(
            "ghost", src=tmp_path, dist=tmp_path / "dist", validate=False
        )


def test_build_skill_default_commit_uses_git_head(
    tmp_path, make_skill, monkeypatch
):
    src = tmp_path / "skills"
    make_skill("demo", commit=None, parent=src)
    dist = tmp_path / "dist"
    monkeypatch.setattr(build, "git_head_commit", lambda _dir: "deadbee")

    out = build.build_skill("demo", src=src, dist=dist, validate=False)

    assert metadata.read_source_commit(out / "SKILL.md") == "deadbee"


@pytest.fixture
def skills_ref(monkeypatch):
    skills_ref = mock.Mock(spec_set=["validate"])
    monkeypatch.setattr(build, "skills_ref", skills_ref)
    return skills_ref


def test_build_skill_validate_success(tmp_path, make_skill, skills_ref):
    src = tmp_path / "skills"
    make_skill("demo", parent=src)
    dist = tmp_path / "dist"
    skills_ref.validate.return_value = []

    out = build.build_skill("demo", src=src, dist=dist, validate=True)

    assert (out / "SKILL.md").is_file()
    skills_ref.validate.assert_called_once_with(dist / "demo")


def test_build_skill_validate_failure(tmp_path, make_skill, skills_ref):
    src = tmp_path / "skills"
    make_skill("demo", parent=src)
    dist = tmp_path / "dist"
    skills_ref.validate.return_value = ["test error"]

    with pytest.raises(build.ValidationFailed):
        build.build_skill("demo", src=src, dist=dist, validate=True)

    skills_ref.validate.assert_called_once_with(dist / "demo")


def test_build_skill_unstamped_without_commit(
    tmp_path, make_skill, monkeypatch
):
    src = tmp_path / "skills"
    make_skill("demo", commit=None, parent=src)
    dist = tmp_path / "dist"
    monkeypatch.setattr(build, "git_head_commit", lambda _dir: None)

    out = build.build_skill("demo", src=src, dist=dist, validate=False)

    assert metadata.read_source_commit(out / "SKILL.md") is None


def test_git_head_commit_returns_sha(tmp_path, monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda _name: "/bin/git")
    completed = subprocess.CompletedProcess([], 0, stdout="deadbee\n")
    monkeypatch.setattr(build.subprocess, "run", lambda *a, **k: completed)

    result = build.git_head_commit(tmp_path)

    assert result == "deadbee"


def test_git_head_commit_handles_git_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(build.shutil, "which", lambda _name: "/bin/git")

    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, ["git"])

    monkeypatch.setattr(build.subprocess, "run", boom)

    result = build.git_head_commit(tmp_path)

    assert result is None
