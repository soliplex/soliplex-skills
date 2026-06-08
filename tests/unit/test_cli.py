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
    monkeypatch.setattr(releases, "fetch", _serve({}))  # no 'latest' pointer

    rc = cli.main(["list", "--pyproject", str(pp)])

    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines()[0].startswith("TAG")  # header row
    assert "docs-2026.05.29-bbbbbbb" in out
    assert "rolling" in out


def test_list_json(tmp_path, monkeypatch, capsys):
    pp = _write_pyproject(tmp_path, _DOCS)
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: [])
    monkeypatch.setattr(releases, "fetch", _serve({}))  # no 'latest' pointer

    rc = cli.main(["list", "--pyproject", str(pp), "--json"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == []


def test_list_marks_installed_and_latest_rows(
    tmp_path, monkeypatch, make_skill, make_tarball, capsys
):
    pp = _write_pyproject(tmp_path, _DOCS)
    raw = [
        {
            "tag_name": "docs-2026.05.29-bbbbbbb",
            "published_at": "2026-05-29T00:00:00Z",
            "assets": [{"name": "soliplex-docs-skill.tar.gz"}],
            "target_commitish": "main",
            "prerelease": True,
        },
        {
            "tag_name": "docs-2026.05.18-aaaaaaa",
            "published_at": "2026-05-18T00:00:00Z",
            "assets": [{"name": "soliplex-docs-skill.tar.gz"}],
            "target_commitish": "main",
            "prerelease": True,
        },
    ]
    monkeypatch.setattr(releases, "list_releases", lambda owner, repo: raw)
    installed = make_skill(
        "soliplex-docs", commit="aaaaaaa", parent=tmp_path / "installed"
    )
    monkeypatch.setattr(
        releases,
        "fetch",
        _serve(_publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")),
    )

    rc = cli.main(
        ["list", "--pyproject", str(pp), "--skill-dir", str(installed)]
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    installed_line = next(ln for ln in lines if "aaaaaaa" in ln)
    latest_line = next(ln for ln in lines if "bbbbbbb" in ln)
    assert installed_line.endswith("← installed")
    assert latest_line.endswith("← latest")


def test_diff_returns_one_and_prints_diff_on_changes(
    tmp_path, monkeypatch, make_skill, make_tarball, capsys
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

    out = capsys.readouterr().out
    assert rc == 1  # differences were found
    assert "~ changed: references/a.md" in out  # per-file summary
    assert "-old" in out  # the unified diff itself
    assert "+hi" in out


def _serve_two_tags(
    make_skill, make_tarball, tmp_path, left_files, right_files
):
    left = make_skill(
        "soliplex-docs",
        commit="aaaaaaa",
        files=left_files,
        parent=tmp_path / "left",
    )
    right = make_skill(
        "soliplex-docs",
        commit="bbbbbbb",
        files=right_files,
        parent=tmp_path / "right",
    )
    left_tb = make_tarball(left, tmp_path / "left.tar.gz")
    right_tb = make_tarball(right, tmp_path / "right.tar.gz")
    return _serve(
        {
            "docs-1/soliplex-docs-skill.tar.gz": left_tb.read_bytes(),
            "docs-2/soliplex-docs-skill.tar.gz": right_tb.read_bytes(),
        }
    )


def test_diff_two_tags_returns_one_and_prints_diff(
    tmp_path, monkeypatch, make_skill, make_tarball, capsys
):
    pp = _write_pyproject(tmp_path, _DOCS)
    fetch = _serve_two_tags(
        make_skill,
        make_tarball,
        tmp_path,
        {"references/a.md": "old\n"},
        {"references/a.md": "new\n"},
    )
    monkeypatch.setattr(releases, "fetch", fetch)

    rc = cli.main(["diff", "--pyproject", str(pp), "docs-1", "docs-2"])

    out = capsys.readouterr().out
    assert rc == 1  # differences were found
    assert "~ changed: references/a.md" in out  # per-file summary
    assert "-old" in out  # the unified diff itself
    assert "+new" in out


def test_diff_two_tags_identical_returns_zero(
    tmp_path, monkeypatch, make_skill, make_tarball, capsys
):
    pp = _write_pyproject(tmp_path, _DOCS)
    same = {"references/a.md": "same\n"}
    monkeypatch.setattr(
        releases,
        "fetch",
        _serve_two_tags(make_skill, make_tarball, tmp_path, same, same),
    )

    rc = cli.main(["diff", "--pyproject", str(pp), "docs-1", "docs-2"])

    out = capsys.readouterr().out
    assert rc == 0  # the two sides are identical
    assert "No differences." in out


def test_diff_without_skill_dir_or_other_errors(tmp_path, capsys):
    pp = _write_pyproject(tmp_path, _DOCS)

    rc = cli.main(["diff", "--pyproject", str(pp)])

    assert rc == 2  # invalid invocation
    assert "needs --skill-dir" in capsys.readouterr().err


def test_diff_help_documents_output_and_exit_codes(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["diff", "--help"])

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "unified diff" in out  # explains what is printed
    assert "exit status:" in out  # documents the return codes
    assert "0  the two sides are identical" in out
    assert "1  differences were found" in out


def test_list_help_documents_output_and_exit_codes(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["list", "--help"])

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "table is printed" in out  # explains what is printed
    assert "exit status:" in out  # documents the return codes
    assert "0  versions listed" in out


def test_upgrade_help_documents_output_and_exit_codes(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["upgrade", "--help"])

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "install it over --skill-dir" in out  # explains the effect
    assert "exit status:" in out  # documents the return codes
    assert "0  upgraded, or already up to date" in out


def test_build_help_documents_output_and_exit_codes(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--help"])

    out = capsys.readouterr().out
    assert exc.value.code == 0
    assert "agent-skills validator" in out  # explains what it does
    assert "exit status:" in out  # documents the return codes
    assert "1  no skills found under --src" in out


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
    monkeypatch.setattr(releases, "fetch", _serve({}))  # no 'latest' pointer

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
