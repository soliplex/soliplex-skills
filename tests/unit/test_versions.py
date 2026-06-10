"""Tests for :mod:`soliplex_skills.versions` (offline)."""

from __future__ import annotations

import json
import re
from dataclasses import fields

import pytest

from soliplex_skills import _archive
from soliplex_skills import metadata
from soliplex_skills import releases
from soliplex_skills import versions

_ROLLING_RE = re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$")


def _spec():
    return versions.SkillSpec(
        owner="soliplex",
        repo="soliplex",
        skill_name="soliplex-docs",
        asset_tarball="soliplex-docs-skill.tar.gz",
        pointer_tag="docs-latest",
        rolling_re=_ROLLING_RE,
    )


def _skill_md(commit, body):
    """Render a SKILL.md with a stamped ``source_commit`` and a custom body."""
    return (
        f"---\nname: soliplex-docs\n"
        f'description: "Soliplex docs."\nmetadata:\n'
        f'  source_commit: "{commit}"\n---\n\n{body}'
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

    assert spec.pointer_manifest == "latest.json"
    assert "compare_scope" not in {field.name for field in fields(spec)}


def test_skill_spec_compare_scope_is_deprecated():
    with pytest.warns(DeprecationWarning, match="compare_scope is deprecated"):
        versions.SkillSpec(
            owner="soliplex",
            repo="soliplex",
            skill_name="soliplex-docs",
            asset_tarball="soliplex-docs-skill.tar.gz",
            pointer_tag="docs-latest",
            rolling_re=_ROLLING_RE,
            compare_scope="references",
        )


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


def test_list_marks_installed_and_latest(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    raw = [
        _release("docs-2026.05.29-bbbbbbb", date="2026-05-29"),
        _release("docs-2026.05.18-aaaaaaa", date="2026-05-18"),
    ]
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: raw)
    installed = make_skill(
        "soliplex-docs", commit="aaaaaaa", parent=tmp_path / "installed"
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"references/a.md": "x\n"},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    result = versions.SkillVersions(_spec()).list(
        installed_path=installed, mark_latest=True
    )

    by_tag = {row["tag"]: row for row in result}
    assert by_tag["docs-2026.05.18-aaaaaaa"]["installed"] is True
    assert by_tag["docs-2026.05.18-aaaaaaa"]["latest"] is False
    assert by_tag["docs-2026.05.29-bbbbbbb"]["latest"] is True
    assert by_tag["docs-2026.05.29-bbbbbbb"]["installed"] is False


def test_list_mark_latest_pointer_unavailable(monkeypatch):
    raw = [_release("docs-2026.05.18-aaaaaaa", date="2026-05-18")]
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: raw)
    monkeypatch.setattr(releases, "fetch", _serve({}))

    result = versions.SkillVersions(_spec()).list(mark_latest=True)

    assert result[0]["latest"] is False
    assert result[0]["installed"] is False


def test_format_list_table_renders_header_and_marks():
    rows = [
        {
            "tag": "docs-2026.05.29-bbbbbbb",
            "date": "2026-05-29",
            "kind": "rolling",
            "commit": "bbbbbbb",
            "installed": True,
            "latest": True,
        },
        {
            "tag": "v0.68",
            "date": "2026-05-20",
            "kind": "release",
            "commit": "a1b2c3d",
            "installed": False,
            "latest": False,
        },
    ]

    table = versions.format_list_table(rows)

    lines = table.splitlines()
    assert lines[0].startswith("TAG")
    assert lines[1].endswith("← installed, latest")
    assert lines[2].endswith("a1b2c3d")


def test_format_list_table_empty():
    table = versions.format_list_table([])

    assert table == "No published versions found."


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

    rc = versions.SkillVersions(_spec()).diff(
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


def test_diff_ignores_source_commit_stamp(
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
        make_skill, make_tarball, tmp_path, commit="bbbbbbb", files=files
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    assert rc == 0
    assert "No differences." in capsys.readouterr().out


def _stamped_md(*, commit, generated="2026-05-29", version=None):
    """Render a SKILL.md whose metadata carries the given build stamps."""
    stamps = [f'  source_commit: "{commit}"', f'  generated: "{generated}"']
    if version is not None:
        stamps.insert(0, f'  version: "{version}"')
    front = "\n".join(stamps)
    return (
        f'---\nname: soliplex-docs\ndescription: "Soliplex docs."\n'
        f"metadata:\n{front}\n---\n\n# Demo skill\n"
    )


def test_diff_ignores_generated_stamp(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={
            "SKILL.md": _stamped_md(commit="aaaaaaa", generated="2026-01-01")
        },
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={
            "SKILL.md": _stamped_md(commit="bbbbbbb", generated="2026-12-31")
        },
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    assert rc == 0
    assert "No differences." in capsys.readouterr().out


def test_diff_reports_version_difference(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"SKILL.md": _stamped_md(commit="aaaaaaa", version="1.0.0")},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"SKILL.md": _stamped_md(commit="bbbbbbb", version="2.0.0")},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    assert rc == 1
    assert "~ changed: SKILL.md" in capsys.readouterr().out


def test_normalize_skill_md_without_metadata_block(tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        '---\nname: soliplex-docs\ndescription: "d"\n---\n\n# Body\n',
        encoding="utf-8",
    )

    lines = versions._normalize_skill_md(skill_md)

    assert "name: soliplex-docs" in lines
    assert not any(line.startswith("metadata.") for line in lines)


def test_normalize_skill_md_unparseable_falls_back(tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("no frontmatter here\n", encoding="utf-8")

    lines = versions._normalize_skill_md(skill_md)

    assert lines == ["no frontmatter here"]


def test_diff_reports_skill_md_body_change(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    old_md = _skill_md("aaaaaaa", "# Documentation map\n- old.md\n")
    new_md = _skill_md("bbbbbbb", "# Documentation map\n- new.md\n")
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"SKILL.md": old_md},
        parent=tmp_path / "installed",
    )
    mapping, _ = _publish(
        make_skill,
        make_tarball,
        tmp_path,
        commit="bbbbbbb",
        files={"SKILL.md": new_md},
    )
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff(installed, "latest")

    out = capsys.readouterr().out
    assert rc == 1
    assert "~ changed: SKILL.md" in out


def _publish_tag(make_skill, make_tarball, tmp_path, *, tag, commit, files):
    """Publish a tarball addressable by ``<tag>/<asset>`` (no pointer)."""
    skill = make_skill(
        "soliplex-docs", commit=commit, files=files, parent=tmp_path / tag
    )
    tarball = make_tarball(skill, tmp_path / f"{tag}.tar.gz")
    return {f"{tag}/soliplex-docs-skill.tar.gz": tarball.read_bytes()}


def test_diff_published_reports_changes(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    mapping = {
        **_publish_tag(
            make_skill,
            make_tarball,
            tmp_path,
            tag="docs-2026.05.20-aaaaaaa",
            commit="aaaaaaa",
            files={"references/a.md": "old\n"},
        ),
        **_publish_tag(
            make_skill,
            make_tarball,
            tmp_path,
            tag="docs-2026.05.29-bbbbbbb",
            commit="bbbbbbb",
            files={"references/a.md": "new\n"},
        ),
    }
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff_published(
        "docs-2026.05.20-aaaaaaa", "docs-2026.05.29-bbbbbbb"
    )

    out = capsys.readouterr().out
    assert rc == 1
    assert "~ changed: references/a.md" in out


def test_diff_published_identical_returns_zero(
    monkeypatch, tmp_path, make_skill, make_tarball, capsys
):
    files = {"references/a.md": "same\n"}
    mapping = {
        **_publish_tag(
            make_skill,
            make_tarball,
            tmp_path,
            tag="docs-2026.05.20-aaaaaaa",
            commit="aaaaaaa",
            files=files,
        ),
        **_publish_tag(
            make_skill,
            make_tarball,
            tmp_path,
            tag="docs-2026.05.29-bbbbbbb",
            commit="bbbbbbb",
            files=files,
        ),
    }
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    rc = versions.SkillVersions(_spec()).diff_published(
        "docs-2026.05.20-aaaaaaa", "docs-2026.05.29-bbbbbbb"
    )

    assert rc == 0
    assert "No differences." in capsys.readouterr().out


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
