"""Tests for :mod:`soliplex_skills.install` (offline)."""

from __future__ import annotations

import json

import pytest
import skills_ref

from soliplex_skills import _archive
from soliplex_skills import exceptions
from soliplex_skills import install
from soliplex_skills import releases

_INSTALLED_BY = "installer-skill"
_SKILL_NAME = "dummy-skill"
_ASSET_TARBALL = f"{_SKILL_NAME}.tar.gz"
_POINTER_TAG = f"{_SKILL_NAME.split('-')[0]}-latest"
_ROLLING_DATE = "2026.05.29"
_ROLLING_PREFIX = _SKILL_NAME.split("-")[0]
_RELEASE_TAG = "v0.68"


def _spec():
    return install.PublishedSkill(
        name=_SKILL_NAME,
        owner="soliplex",
        repo="soliplex",
        asset_tarball=_ASSET_TARBALL,
        pointer_tag=_POINTER_TAG,
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
        _SKILL_NAME,
        commit=commit,
        files={
            "references/a.md": "hi\n",
            "scripts/skill_versions.py": "# helper\n",
        },
        parent=tmp_path / f"pub-{commit}",
    )
    tarball = make_tarball(skill, tmp_path / f"{commit}.tar.gz")
    tag = f"{_ROLLING_PREFIX}-{_ROLLING_DATE}-{commit}"
    manifest = {
        "tag": tag,
        "source_commit": commit,
        "generated": "2026-05-29",
        "sha256": "0" * 64 if bad_sha else _archive.sha256(tarball),
        "asset_url": (
            "https://github.com/soliplex/soliplex/releases/download/"
            f"{tag}/{_ASSET_TARBALL}"
        ),
    }
    return {
        _ASSET_TARBALL: tarball.read_bytes(),
        "latest.json": json.dumps(manifest).encode("utf-8"),
    }


def _skill_with_self_management(
    parent,
    name="dummy-skill",
    *,
    heading="Managing this skill's version",
    compatibility=None,
):
    root = parent / name
    root.mkdir(parents=True, exist_ok=True)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "skill_versions.py").write_text("# helper\n")
    compat = ""
    if compatibility is not None:
        compat = f"compatibility: {compatibility}\n"
    (root / "SKILL.md").write_text(
        f'---\nname: {name}\ndescription: "A dummy skill."\n{compat}---\n\n'
        f"# Title\n\n## {heading}\n\n"
        "Run `uv run scripts/skill_versions.py list` to list versions.\n\n"
        "## Documentation map\n\n- a topic\n",
        encoding="utf-8",
    )
    return root


def _compat_line(text):
    return next(
        (ln for ln in text.splitlines() if ln.startswith("compatibility:")),
        None,
    )


def test_download_base_and_urls():
    spec = _spec()

    base = spec.download_base

    assert base == "https://github.com/soliplex/soliplex/releases/download"
    assert spec.asset_url(_RELEASE_TAG).endswith(
        f"/{_RELEASE_TAG}/{_ASSET_TARBALL}"
    )
    assert spec.pointer_url().endswith(f"/{_POINTER_TAG}/latest.json")


def test_download_skill_via_pointer(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "dl"
    dest.mkdir()

    root = install.download_skill(_spec(), None, dest)

    assert (root / "SKILL.md").is_file()
    assert root.name == _SKILL_NAME


def test_download_skill_explicit_tag(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "dl"
    dest.mkdir()

    root = install.download_skill(
        _spec(), f"{_ROLLING_PREFIX}-{_ROLLING_DATE}-bbbbbbb", dest
    )

    assert (root / "references" / "a.md").read_text() == "hi\n"


def test_download_skill_pointer_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(releases, "fetch", _serve({}))
    dest = tmp_path / "dl"
    dest.mkdir()

    with pytest.raises(exceptions.PointerUnavailable):
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


def test_download_skill_refuses_nonempty_target(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    monkeypatch.setattr(releases, "fetch", _serve({}))  # never reached
    dest = tmp_path / "dl"
    target = dest / _SKILL_NAME
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("mine\n")

    with pytest.raises(exceptions.DestinationNotEmpty):
        install.download_skill(_spec(), None, dest)

    assert (target / "keep.txt").read_text() == "mine\n"


def test_download_skill_force_replaces_nonempty_target(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "dl"
    target = dest / _SKILL_NAME
    target.mkdir(parents=True)
    (target / "stale.txt").write_text("old\n")

    root = install.download_skill(_spec(), None, dest, force=True)

    assert root == target
    assert not (target / "stale.txt").exists()
    assert (root / "SKILL.md").is_file()


@pytest.mark.parametrize("helper, expected", [(True, False), (False, True)])
def test_is_defanged(tmp_path, make_skill, helper, expected):
    files = {"scripts/skill_versions.py": "# helper\n"} if helper else {}
    root = make_skill(_SKILL_NAME, files=files, parent=tmp_path)

    result = install.is_defanged(root)

    assert result is expected


def test_defang_skill_removes_helper_and_empty_scripts_dir(tmp_path):
    root = _skill_with_self_management(tmp_path)

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    assert not (root / "scripts" / "skill_versions.py").exists()
    assert not (root / "scripts").exists()
    assert skills_ref.validate(root) == []


def test_defang_skill_rewrites_only_self_management_section(tmp_path):
    root = _skill_with_self_management(tmp_path)

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "## Managing this skill's version" in skill_md
    assert "uv run scripts/skill_versions.py" not in skill_md
    assert _INSTALLED_BY in skill_md
    assert "from inside the room" in skill_md
    assert "## Documentation map" in skill_md
    assert "- a topic" in skill_md
    assert skills_ref.validate(root) == []


def test_defang_skill_preserves_custom_heading(tmp_path):
    root = _skill_with_self_management(
        tmp_path, heading="Checking for updates"
    )

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    skill_md = (root / "SKILL.md").read_text(encoding="utf-8")
    assert "## Checking for updates" in skill_md
    assert skills_ref.validate(root) == []


def test_defang_skill_removes_pycache(tmp_path):
    root = _skill_with_self_management(tmp_path)
    pycache = root / "scripts" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "skill_versions.cpython-312.pyc").write_text("x")

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    assert not pycache.exists()
    assert not (root / "scripts").exists()
    assert skills_ref.validate(root) == []


def test_defang_skill_keeps_other_scripts(tmp_path):
    root = _skill_with_self_management(tmp_path)
    (root / "scripts" / "other.py").write_text("# other\n")

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    assert not (root / "scripts" / "skill_versions.py").exists()
    assert (root / "scripts" / "other.py").is_file()
    assert (root / "scripts").is_dir()
    assert skills_ref.validate(root) == []


def test_defang_skill_no_skill_md(tmp_path):
    root = tmp_path / "skill"
    root.mkdir()
    (root / "scripts").mkdir()
    (root / "scripts" / "skill_versions.py").write_text("# helper\n")

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    assert not (root / "scripts" / "skill_versions.py").exists()
    assert not (root / "scripts").exists()


def test_defang_skill_custom_note(tmp_path):
    root = _skill_with_self_management(tmp_path)

    install.defang_skill(root, installed_by=_INSTALLED_BY, note="CUSTOM\n")

    assert "CUSTOM" in (root / "SKILL.md").read_text(encoding="utf-8")
    assert skills_ref.validate(root) == []


def test_defang_skill_last_section(tmp_path):
    root = tmp_path / "dummy-skill"
    root.mkdir()
    (root / "scripts").mkdir()
    (root / "scripts" / "skill_versions.py").write_text("# helper\n")
    (root / "SKILL.md").write_text(
        '---\nname: dummy-skill\ndescription: "A dummy skill."\n---\n\n'
        "# Title\n\n## Earlier\n\nstuff.\n\n"
        "## Managing this skill's version\n\n"
        "Run `uv run scripts/skill_versions.py list`.\n",
        encoding="utf-8",
    )

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "## Managing this skill's version" in text
    assert "uv run scripts/skill_versions.py" not in text
    assert skills_ref.validate(root) == []


def test_defang_skill_scrubs_compatibility_helper_sentence(tmp_path):
    # Mirrors soliplex-docs: the helper's network/GitHub requirement lives in
    # the compatibility frontmatter, alongside a legitimate first sentence.
    root = _skill_with_self_management(
        tmp_path,
        compatibility=(
            '"The documentation itself needs no special environment. '
            "The bundled scripts/skill_versions.py requires Python 3.12+ and "
            "network access to api.github.com / github.com "
            '(honors GITHUB_TOKEN / GH_TOKEN)."'
        ),
    )

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert _compat_line(text) == (
        'compatibility: "The documentation itself needs no special '
        'environment."'
    )
    assert "github.com" not in text
    assert "GITHUB_TOKEN" not in text
    assert skills_ref.validate(root) == []


def test_defang_skill_drops_compatibility_line_when_all_helper(tmp_path):
    # The whole value is about the soliplex-skills helper -> line removed.
    root = _skill_with_self_management(
        tmp_path,
        compatibility=(
            '"Backed by the soliplex-skills library; needs network access '
            'to github.com."'
        ),
    )

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert _compat_line(text) is None
    assert "soliplex-skills" not in text
    assert skills_ref.validate(root) == []


def test_defang_skill_keeps_unrelated_compatibility(tmp_path):
    unrelated = '"The documentation itself needs no special environment."'
    root = _skill_with_self_management(tmp_path, compatibility=unrelated)

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert _compat_line(text) == (
        'compatibility: "The documentation itself needs no special '
        'environment."'
    )
    assert skills_ref.validate(root) == []


def test_defang_skill_scrubs_unquoted_compatibility(tmp_path):
    root = _skill_with_self_management(
        tmp_path,
        compatibility=(
            "Docs need nothing. The scripts/skill_versions.py helper needs "
            "the network."
        ),
    )

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert _compat_line(text) == "compatibility: Docs need nothing."
    assert skills_ref.validate(root) == []


def test_defang_skill_no_frontmatter(tmp_path):
    root = tmp_path / "dummy-skill"
    root.mkdir()
    (root / "scripts").mkdir()
    (root / "scripts" / "skill_versions.py").write_text("# helper\n")
    (root / "SKILL.md").write_text(
        "# Title\n\n## Updating\n\nRun `scripts/skill_versions.py upgrade`.\n",
        encoding="utf-8",
    )

    install.defang_skill(root, installed_by=_INSTALLED_BY)

    text = (root / "SKILL.md").read_text(encoding="utf-8")
    assert not (root / "scripts" / "skill_versions.py").exists()
    assert "## Updating" in text
    assert "from inside the room" in text


def test_install_skill_adds_and_defangs_by_default(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill(
        _spec(), None, dest, installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.ADDED
    assert root == dest / _SKILL_NAME
    assert (root / "SKILL.md").is_file()
    assert not (root / "scripts" / "skill_versions.py").exists()


def test_install_skill_no_defang_keeps_helper(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill(
        _spec(), None, dest, installed_by=_INSTALLED_BY, defang=False
    )

    assert status is install.InstallStatus.ADDED
    assert (root / "scripts" / "skill_versions.py").is_file()


def test_install_skill_upgrades_existing_copy(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "installed",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill(
        _spec(), None, dest, installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.ADDED
    assert (root / "references" / "a.md").read_text() == "hi\n"


def test_install_skill_noop_when_commit_matches(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="aaaaaaa")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    root, status = install.install_skill(
        _spec(), None, tmp_path / "skills", installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.UNCHANGED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_install_skill_force_reinstalls_same_commit(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="aaaaaaa")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    root, status = install.install_skill(
        _spec(),
        None,
        tmp_path / "skills",
        installed_by=_INSTALLED_BY,
        force=True,
    )

    assert status is install.InstallStatus.REINSTALLED
    assert (root / "references" / "a.md").read_text() == "hi\n"


def test_install_skill_dry_run_refuses_version_mismatch(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    # Only the pointer is served; the refusal is decided without the asset.
    monkeypatch.setattr(
        releases, "fetch", _serve({"latest.json": mapping["latest.json"]})
    )
    dest = tmp_path / "skills"

    with pytest.raises(exceptions.VersionMismatch):
        install.install_skill(
            _spec(), None, dest, installed_by=_INSTALLED_BY, dry_run=True
        )

    assert (dest / _SKILL_NAME / "references" / "a.md").read_text() == "old\n"


def test_install_skill_refuses_version_mismatch(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="aaaaaaa",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "skills"

    with pytest.raises(exceptions.VersionMismatch):
        install.install_skill(_spec(), None, dest, installed_by=_INSTALLED_BY)

    assert (dest / _SKILL_NAME / "references" / "a.md").read_text() == "old\n"


def test_install_skill_dry_run_does_not_download_asset(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    # Serve only the pointer manifest; fetching the asset would raise.
    monkeypatch.setattr(
        releases, "fetch", _serve({"latest.json": mapping["latest.json"]})
    )
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill(
        _spec(), None, dest, installed_by=_INSTALLED_BY, dry_run=True
    )

    assert status is install.InstallStatus.ADDED
    assert not root.exists()


def test_install_skill_dry_run_unchanged_when_pointer_matches(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="bbbbbbb",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(
        releases, "fetch", _serve({"latest.json": mapping["latest.json"]})
    )
    dest = tmp_path / "skills"

    root, status = install.install_skill(
        _spec(), None, dest, installed_by=_INSTALLED_BY, dry_run=True
    )

    assert status is install.InstallStatus.UNCHANGED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_install_skill_dry_run_reinstall_when_forced(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="bbbbbbb",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(
        releases, "fetch", _serve({"latest.json": mapping["latest.json"]})
    )
    dest = tmp_path / "skills"

    root, status = install.install_skill(
        _spec(),
        None,
        dest,
        installed_by=_INSTALLED_BY,
        force=True,
        dry_run=True,
    )

    assert status is install.InstallStatus.REINSTALLED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_install_skill_dry_run_explicit_tag_downloads_to_classify(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    make_skill(
        _SKILL_NAME,
        commit="bbbbbbb",
        files={"references/a.md": "old\n"},
        parent=tmp_path / "skills",
    )
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "skills"

    # An explicit tag carries no pointer, so the dry-run downloads to classify.
    root, status = install.install_skill(
        _spec(),
        f"{_ROLLING_PREFIX}-{_ROLLING_DATE}-bbbbbbb",
        dest,
        installed_by=_INSTALLED_BY,
        dry_run=True,
    )

    assert status is install.InstallStatus.UNCHANGED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_install_skill_dry_run_pointer_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(releases, "fetch", _serve({}))
    dest = tmp_path / "skills"
    dest.mkdir()

    with pytest.raises(exceptions.PointerUnavailable):
        install.install_skill(
            _spec(), None, dest, installed_by=_INSTALLED_BY, dry_run=True
        )


def _local_skill(make_skill, tmp_path, *, commit, body="hi\n", helper=False):
    """A local source skill dir for the install/upgrade ``_from`` tests."""
    files = {"references/a.md": body}
    if helper:
        files["scripts/skill_versions.py"] = "# helper\n"
    return make_skill(
        _SKILL_NAME, commit=commit, files=files, parent=tmp_path / "src"
    )


def _installed_skill(make_skill, tmp_path, *, commit, body="old\n"):
    """An already-installed skill under the ``<dest>`` the tests use."""
    make_skill(
        _SKILL_NAME,
        commit=commit,
        files={"references/a.md": body},
        parent=tmp_path / "skills",
    )
    return tmp_path / "skills"


# --------------------------------------------------------------------------
# install_skill_from (install-only)
# --------------------------------------------------------------------------
def test_install_skill_from_adds_and_defangs_by_default(tmp_path, make_skill):
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", helper=True)
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill_from(
        src, dest, installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.ADDED
    assert root == dest / _SKILL_NAME
    assert (root / "SKILL.md").is_file()
    assert not (root / "scripts" / "skill_versions.py").exists()


def test_install_skill_from_does_not_modify_source(tmp_path, make_skill):
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", helper=True)
    dest = tmp_path / "skills"
    dest.mkdir()

    install.install_skill_from(src, dest, installed_by=_INSTALLED_BY)

    assert (src / "scripts" / "skill_versions.py").read_text() == "# helper\n"


def test_install_skill_from_no_defang_keeps_helper(tmp_path, make_skill):
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", helper=True)
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill_from(
        src, dest, installed_by=_INSTALLED_BY, defang=False
    )

    assert (root / "scripts" / "skill_versions.py").is_file()


def test_install_skill_from_unchanged_when_commit_matches(
    tmp_path, make_skill
):
    dest = _installed_skill(make_skill, tmp_path, commit="bbbbbbb")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    root, status = install.install_skill_from(
        src, dest, installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.UNCHANGED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_install_skill_from_force_reinstalls_same_commit(tmp_path, make_skill):
    dest = _installed_skill(make_skill, tmp_path, commit="bbbbbbb")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    root, status = install.install_skill_from(
        src, dest, installed_by=_INSTALLED_BY, force=True
    )

    assert status is install.InstallStatus.REINSTALLED
    assert (root / "references" / "a.md").read_text() == "new\n"


def test_install_skill_from_refuses_version_mismatch(tmp_path, make_skill):
    dest = _installed_skill(make_skill, tmp_path, commit="aaaaaaa")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    with pytest.raises(exceptions.VersionMismatch):
        install.install_skill_from(src, dest, installed_by=_INSTALLED_BY)

    assert (dest / _SKILL_NAME / "references" / "a.md").read_text() == "old\n"


def test_install_skill_from_dry_run_writes_nothing(tmp_path, make_skill):
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb")
    dest = tmp_path / "skills"
    dest.mkdir()

    root, status = install.install_skill_from(
        src, dest, installed_by=_INSTALLED_BY, dry_run=True
    )

    assert status is install.InstallStatus.ADDED
    assert not root.exists()


def test_install_skill_from_rejects_invalid_skill(tmp_path):
    src = tmp_path / "wrong-name"
    src.mkdir()
    (src / "SKILL.md").write_text(
        '---\nname: soliplex-docs\ndescription: "A skill."\n---\n\n# Title\n'
    )
    dest = tmp_path / "skills"
    dest.mkdir()

    with pytest.raises(exceptions.SourceInvalid):
        install.install_skill_from(src, dest, installed_by=_INSTALLED_BY)


# --------------------------------------------------------------------------
# upgrade_skill_from (upgrade-only)
# --------------------------------------------------------------------------
def test_upgrade_skill_from_upgrades_existing(tmp_path, make_skill):
    dest = _installed_skill(make_skill, tmp_path, commit="aaaaaaa")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    root, status = install.upgrade_skill_from(
        src, dest, installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.UPGRADED
    assert (root / "references" / "a.md").read_text() == "new\n"


def test_upgrade_skill_from_unchanged_when_commit_matches(
    tmp_path, make_skill
):
    dest = _installed_skill(make_skill, tmp_path, commit="bbbbbbb")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    root, status = install.upgrade_skill_from(
        src, dest, installed_by=_INSTALLED_BY
    )

    assert status is install.InstallStatus.UNCHANGED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_upgrade_skill_from_force_reinstalls_same_commit(tmp_path, make_skill):
    dest = _installed_skill(make_skill, tmp_path, commit="bbbbbbb")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    root, status = install.upgrade_skill_from(
        src, dest, installed_by=_INSTALLED_BY, force=True
    )

    assert status is install.InstallStatus.REINSTALLED
    assert (root / "references" / "a.md").read_text() == "new\n"


def test_upgrade_skill_from_refuses_de_novo(tmp_path, make_skill):
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb")
    dest = tmp_path / "skills"
    dest.mkdir()

    with pytest.raises(exceptions.NotInstalled):
        install.upgrade_skill_from(src, dest, installed_by=_INSTALLED_BY)

    assert not (dest / _SKILL_NAME).exists()


def test_upgrade_skill_from_dry_run_writes_nothing(tmp_path, make_skill):
    dest = _installed_skill(make_skill, tmp_path, commit="aaaaaaa")
    src = _local_skill(make_skill, tmp_path, commit="bbbbbbb", body="new\n")

    root, status = install.upgrade_skill_from(
        src, dest, installed_by=_INSTALLED_BY, dry_run=True
    )

    assert status is install.InstallStatus.UPGRADED
    assert (root / "references" / "a.md").read_text() == "old\n"


# --------------------------------------------------------------------------
# upgrade_skill (published)
# --------------------------------------------------------------------------
def test_upgrade_skill_refuses_de_novo(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))
    dest = tmp_path / "skills"
    dest.mkdir()

    with pytest.raises(exceptions.NotInstalled):
        install.upgrade_skill(_spec(), None, dest, installed_by=_INSTALLED_BY)


def test_upgrade_skill_dry_run_refuses_de_novo(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(
        releases, "fetch", _serve({"latest.json": mapping["latest.json"]})
    )
    dest = tmp_path / "skills"
    dest.mkdir()

    with pytest.raises(exceptions.NotInstalled):
        install.upgrade_skill(
            _spec(), None, dest, installed_by=_INSTALLED_BY, dry_run=True
        )


def test_upgrade_skill_dry_run_reports_upgrade_without_writing(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    dest = _installed_skill(make_skill, tmp_path, commit="aaaaaaa")
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(
        releases, "fetch", _serve({"latest.json": mapping["latest.json"]})
    )

    root, status = install.upgrade_skill(
        _spec(), None, dest, installed_by=_INSTALLED_BY, dry_run=True
    )

    assert status is install.InstallStatus.UPGRADED
    assert (root / "references" / "a.md").read_text() == "old\n"


def test_upgrade_skill_dry_run_explicit_tag_downloads_to_classify(
    monkeypatch, tmp_path, make_skill, make_tarball
):
    dest = _installed_skill(make_skill, tmp_path, commit="aaaaaaa")
    mapping = _publish(make_skill, make_tarball, tmp_path, commit="bbbbbbb")
    monkeypatch.setattr(releases, "fetch", _serve(mapping))

    root, status = install.upgrade_skill(
        _spec(),
        f"{_ROLLING_PREFIX}-{_ROLLING_DATE}-bbbbbbb",
        dest,
        installed_by=_INSTALLED_BY,
        dry_run=True,
    )

    assert status is install.InstallStatus.UPGRADED
    assert (root / "references" / "a.md").read_text() == "old\n"
