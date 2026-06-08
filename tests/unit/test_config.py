"""Tests for :mod:`soliplex_skills.config` (offline)."""

from __future__ import annotations

from dataclasses import fields

import pytest

from soliplex_skills import config

_DOCS = {
    "name": "soliplex-docs",
    "owner": "soliplex",
    "repo": "soliplex",
    "asset_tarball": "soliplex-docs-skill.tar.gz",
    "pointer_tag": "docs-latest",
    "rolling_prefix": "docs",
}
_TEMPLATE = {
    "name": "soliplex-template",
    "owner": "soliplex",
    "repo": "soliplex-template",
    "asset_tarball": "soliplex-template-skill.tar.gz",
    "pointer_tag": "template-skill-latest",
    "rolling_prefix": "template-skill",
}


def _write_pyproject(tmp_path, *skills):
    blocks = []
    for skill in skills:
        lines = ["[[tool.soliplex-skills.skill]]"]
        lines += [f'{key} = "{value}"' for key, value in skill.items()]
        blocks.append("\n".join(lines))
    path = tmp_path / "pyproject.toml"
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return path


def test_load_single_skill(tmp_path):
    path = _write_pyproject(tmp_path, _DOCS)

    specs = config.load_skill_specs(path)

    spec = specs["soliplex-docs"]
    assert set(specs) == {"soliplex-docs"}
    assert spec.rolling_re.match("docs-2026.05.29-cc9a290")
    assert not spec.rolling_re.match("template-skill-2026.05.29-cc9a290")


def test_load_multiple_skills(tmp_path):
    path = _write_pyproject(tmp_path, _DOCS, _TEMPLATE)

    specs = config.load_skill_specs(path)

    assert set(specs) == {"soliplex-docs", "soliplex-template"}


def test_legacy_compare_scope_key_is_ignored(tmp_path):
    path = _write_pyproject(
        tmp_path, {**_TEMPLATE, "compare_scope": "references"}
    )

    specs = config.load_skill_specs(path)

    spec = specs["soliplex-template"]
    assert "compare_scope" not in {field.name for field in fields(spec)}


def test_missing_required_key_raises(tmp_path):
    broken = {key: value for key, value in _DOCS.items() if key != "owner"}
    path = _write_pyproject(tmp_path, broken)

    with pytest.raises(config.SkillConfigError, match="owner"):
        config.load_skill_specs(path)


def test_no_entries_raises(tmp_path):
    path = tmp_path / "pyproject.toml"
    path.write_text('[project]\nname = "x"\n', encoding="utf-8")

    with pytest.raises(config.SkillConfigError):
        config.load_skill_specs(path)


def test_find_pyproject_searches_upward(tmp_path):
    _write_pyproject(tmp_path, _DOCS)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)

    found = config.find_pyproject(nested)

    assert found == tmp_path / "pyproject.toml"


def test_find_pyproject_absent_raises(tmp_path):
    with pytest.raises(config.SkillConfigError):
        config.find_pyproject(tmp_path)
