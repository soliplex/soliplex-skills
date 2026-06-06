"""Tests for :mod:`soliplex_skills.versions` (offline)."""

from __future__ import annotations

import json
import re

import pytest

from soliplex_skills import _archive
from soliplex_skills import metadata
from soliplex_skills import releases
from soliplex_skills import versions

_ROLLING_RE = re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$")


def _spec(compare_scope="tree"):
    return versions.SkillSpec(
        owner="soliplex",
        repo="soliplex",
        skill_name="soliplex-docs",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
        rolling_re=_ROLLING_RE,
        compare_scope=compare_scope,
    )


def _release(tag, *, date, asset=True, target="main", prerelease=False):
    assets = [{"name": "soliplex-docs-skill.tar.gz"}] if asset else []
    return {
        "tag_name": tag,
        "published_at": f"{date}T12:00:00Z",
        "assets": assets,
        "target_commitish": target,
        "prerelease": prerelease,
    }


def _serve(mapping):
    """Build a fake ``releases.fetch`` mapping URL suffixes to bytes."""

    def _fetch(url, *, accept=None, auth_token=None):
        for suffix, payload in mapping.items():
            if url.endswith(suffix):
                return payload
        raise releases.GitHubAPIError(url, "not mapped")

    return _fetch


def _publish(make_skill, make_tarball, tmp_path, *, commit, files):
    """Create a published tarball + manifest; return (mapping, tag)."""
    skill = make_skill(
        "soliplex-docs",
        commit=commit,
        files=files,
        parent=tmp_path / f"pub-{commit}",
    )
    tarball = make_tarball(skill, tmp_path / f"{commit}.tar.gz")
    tag = f"docs-2026.05.29-{commit}"
    manifest = {
        "tag": tag,
        "source_commit": commit,
        "generated": "2026-05-29",
        "sha256": _archive.sha256(tarball),
        "asset_url": (
            "https://github.com/soliplex/soliplex/releases/download/"
            f"{tag}/soliplex-docs-skill.tar.gz"
        ),
    }
    mapping = {
        "soliplex-docs-skill.tar.gz": tarball.read_bytes(),
        "latest.json": json.dumps(manifest).encode("utf-8"),
    }
    return mapping, tag


def test_skill_spec_optional_defaults():
    spec = versions.SkillSpec(
        owner="soliplex",
        repo="soliplex",
        skill_name="soliplex-docs",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
        rolling_re=_ROLLING_RE,
    )

    assert spec.compare_scope == "tree"
    assert spec.pointer_manifest == "latest.json"


def test_list_excludes_pointer_and_assetless_sorts_newest_first(monkeypatch):
    raw = [
        _release("docs-latest", date="2026-06-01"),
        _release("docs-2026.05.18-aaaaaaa", date="2026-05-18"),
        _release("no-asset", date="2026-05-20", asset=False),
        _release("docs-2026.05.29-bbbbbbb", date="2026-05-29"),
        _release("v0.68", date="2026-05-25", target="cc9a290f1111"),
    ]
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: raw)

    result = versions.SkillVersions(_spec()).list()

    tags = [item["tag"] for item in result]
    assert tags == [
        "docs-2026.05.29-bbbbbbb",
        "v0.68",
        "docs-2026.05.18-aaaaaaa",
    ]
    assert result[1]["kind"] == "release"
    assert result[1]["commit"] == "cc9a290"


def test_list_kind_filter(monkeypatch):
    raw = [
        _release("docs-2026.05.29-bbbbbbb", date="2026-05-29"),
        _release("v0.68", date="2026-05-25", target="cc9a290f1111"),
    ]
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: raw)

    result = versions.SkillVersions(_spec()).list(kind="rolling")

    assert [item["tag"] for item in result] == ["docs-2026.05.29-bbbbbbb"]


def test_diff_tree_reports_changes(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "old\n", "scripts/gone.py": "x\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "new\n", "references/added.md": "hi\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    out = capsys.readouterr().out
    assert rc == 1
    assert "~ changed: references/a.md" in out
    assert "+ added:   references/added.md" in out
    assert "- removed: scripts/gone.py" in out


def test_diff_name_only(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "new\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(
        installed, "latest", name_only=True
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert "~ changed: references/a.md" in out
    assert "@@" not in out


def test_diff_explicit_tag(monkeypatch, tmp_path, make_skill, make_tarball):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "same\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "same\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec("references")).diff(
        installed, "docs-2026.05.29-bbbbbbb"
    )

    assert rc == 0


def test_diff_tree_scope_ignores_pycache(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    pycache = {
        "references/a.md": "same\n",
        "scripts/__pycache__/tool.pyc": "junk\n",
    }
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files=pycache,
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill, make_tarball, tmp_path, commit="aaaaaaa", files=pycache
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    assert rc == 0


def test_diff_references_scope_missing_installed_refs(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    installed = make_skill(
        "soliplex-docs", commit="aaaaaaa", parent=tmp_path / "installed"
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "new\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec("references")).diff(installed, "latest")

    assert rc == 1


def test_diff_identical_returns_zero(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    files = {"references/a.md": "same\n"}
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files=files,
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill, make_tarball, tmp_path, commit="aaaaaaa", files=files
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    assert rc == 0
    assert "No differences." in capsys.readouterr().out


def test_diff_references_scope_ignores_non_references(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "same\n", "scripts/tool.py": "v1\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "same\n", "scripts/tool.py": "v2\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec("references")).diff(installed, "latest")

    assert rc == 0


def test_upgrade_installs_new_commit(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "new\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).upgrade(installed, "latest")

    assert rc == 0
    assert (installed / "references" / "a.md").read_text() == "new\n"
    assert metadata.read_source_commit(installed / "SKILL.md") == "bbbbbbb"


def test_upgrade_noop_when_current(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "x\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="aaaaaaa",
        files={"references/a.md": "y\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).upgrade(installed, "latest")

    assert rc == 0
    assert "Already up to date" in capsys.readouterr().out
    assert (installed / "references" / "a.md").read_text() == "x\n"


def test_upgrade_dry_run_writes_nothing(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "new\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).upgrade(
        installed, "latest", dry_run=True
    )

    assert rc == 0
    assert (installed / "references" / "a.md").read_text() == "old\n"


def test_resolve_latest_pointer_unavailable(monkeypatch, tmp_path, make_skill):
    installed = make_skill("soliplex-docs", parent=tmp_path / "installed")
    monkeypatch.setattr(releases, "fetch", _serve({}))

    with pytest.raises(versions.PointerUnavailable):
        versions.SkillVersions(_spec()).upgrade(installed, "latest")
