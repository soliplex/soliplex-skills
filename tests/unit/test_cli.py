"""Tests for :mod:`soliplex_skills.cli` (offline)."""

from __future__ import annotations

import json

import pytest

from soliplex_skills import _archive
from soliplex_skills import cli
from soliplex_skills import releases
from soliplex_skills import versions

_DOCS = {
    "name": "soliplex-docs",
    "owner": "soliplex",
    "repo": "soliplex",
    "asset_tarball": "soliplex-docs-skill.tar.gz",
    "pointer_tag": "docs-latest",
    "rolling_prefix": "docs",
    "compare_scope": "references",
}
_TEMPLATE = {**_DOCS, "name": "soliplex-template", "rolling_prefix": "tmpl"}


def _write_pyproject(tmp_path, *skills):
    blocks = []
    for skill in skills:
        lines = ["[[tool.soliplex-skills.skill]]"]
        lines += [f'{key} = "{value}"' for key, value in skill.items()]
        blocks.append("\n".join(lines))
    path = tmp_path / "pyproject.toml"
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def _serve(mapping):
    def _fetch(url, *, accept=None, auth_token=None):
        for suffix, payload in mapping.items():
            if url.endswith(suffix):
                return payload
        raise releases.GitHubAPIError(url, "not mapped")

    return _fetch


def _publish(make_skill, make_tarball, tmp_path, *, commit):
    skill = make_skill(
        "soliplex-docs",
        commit=commit,
        files={"references/a.md": "hi\n"},
        parent=tmp_path / f"pub-{commit}",
    )
    tarball = make_tarball(skill, tmp_path / f"{commit}.tar.gz")
    manifest = {
        "tag": f"docs-2026.05.29-{commit}",
        "source_commit": commit,
        "generated": "2026-05-29",
        "sha256": _archive.sha256(tarball),
        "asset_url": (
            "https://github.com/soliplex/soliplex/releases/download/"
            f"docs-2026.05.29-{commit}/soliplex-docs-skill.tar.gz"
        ),
    }
    return {
        "soliplex-docs-skill.tar.gz": tarball.read_bytes(),
        "latest.json": json.dumps(manifest).encode("utf-8"),
    }


def test_list_renders_table(tmp_path, monkeypatch, capsys):
    pp = _write_pyproject(tmp_path, _DOCS)
    raw = [
        {
            "tag_name": "docs-2026.05.29-bbbbbbb",
            "published_at": "2026-05-29T00:00:00Z",
            "assets": [{"name": "soliplex-docs-skill.tar.gz"}],
            "target_commitish": "main",
            "prerelease": True,
        }
    ]
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: raw)

    rc = cli.main(["list", "--pyproject", str(pp)])

    out = capsys.readouterr().out
    assert rc == 0
    assert "docs-2026.05.29-bbbbbbb" in out
    assert "rolling" in out


def test_list_json(tmp_path, monkeypatch, capsys):
    pp = _write_pyproject(tmp_path, _DOCS)
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: [])

    rc = cli.main(["list", "--pyproject", str(pp), "--json"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == []


def test_diff_returns_one_on_changes(
    tmp_path, monkeypatch, make_skill, make_tarball
):
    pp = _write_pyproject(tmp_path, _DOCS)
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "installed",
    )
    monkeypatch.setattr(
        releases,
        "fetch",
        _serve(_publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")),
    )

    rc = cli.main(
        ["diff", "--pyproject", str(pp), "--skill-dir", str(installed)]
    )

    assert rc == 1


def test_upgrade_dry_run(tmp_path, monkeypatch, make_skill, make_tarball):
    pp = _write_pyproject(tmp_path, _DOCS)
    installed = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "installed",
    )
    monkeypatch.setattr(
        releases,
        "fetch",
        _serve(_publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")),
    )

    rc = cli.main(
        [
            "upgrade",
            "--pyproject",
            str(pp),
            "--skill-dir",
            str(installed),
            "--dry-run",
        ]
    )

    assert rc == 0
    assert (installed / "references" / "a.md").read_text() == "old\n"


def test_build_all_discovered(tmp_path, make_skill):
    src = tmp_path / "skills"
    make_skill("alpha", commit=None, parent=src)
    make_skill("beta", commit=None, parent=src)
    dist = tmp_path / "dist"

    rc = cli.main(
        [
            "build",
            "--src",
            str(src),
            "--dist",
            str(dist),
            "--commit",
            "abc1234",
            "--no-validate",
        ]
    )

    assert rc == 0
    assert (dist / "alpha" / "SKILL.md").is_file()
    assert (dist / "beta" / "SKILL.md").is_file()


def test_multi_skill_requires_skill_flag(tmp_path, capsys):
    pp = _write_pyproject(tmp_path, _DOCS, _TEMPLATE)

    rc = cli.main(["list", "--pyproject", str(pp)])

    assert rc == 2
    assert "pass --skill" in capsys.readouterr().err


def test_unknown_skill_errors(tmp_path, capsys):
    pp = _write_pyproject(tmp_path, _DOCS)

    rc = cli.main(["list", "--pyproject", str(pp), "--skill", "ghost"])

    assert rc == 2
    assert "no skill 'ghost'" in capsys.readouterr().err


def test_list_selects_named_skill_and_reports_empty(
    tmp_path, monkeypatch, capsys
):
    pp = _write_pyproject(tmp_path, _DOCS, _TEMPLATE)
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: [])

    rc = cli.main(["list", "--pyproject", str(pp), "--skill", "soliplex-docs"])

    assert rc == 0
    assert "No published versions found." in capsys.readouterr().out


def test_build_reports_when_no_skills(tmp_path, capsys):
    src = tmp_path / "empty"
    src.mkdir()

    rc = cli.main(
        ["build", "--src", str(src), "--dist", str(tmp_path / "dist")]
    )

    assert rc == 1
    assert "no skills found" in capsys.readouterr().err


def test_diff_propagates_pointer_unavailable(
    tmp_path, monkeypatch, make_skill
):
    pp = _write_pyproject(tmp_path, _DOCS)
    installed = make_skill("soliplex-docs", parent=tmp_path / "installed")
    monkeypatch.setattr(releases, "fetch", _serve({}))

    with pytest.raises(versions.PointerUnavailable):
        cli.main(
            ["diff", "--pyproject", str(pp), "--skill-dir", str(installed)]
        )
