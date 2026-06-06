"""Tests for :mod:`soliplex_skills.metadata`."""

from __future__ import annotations

import pytest

from soliplex_skills import metadata


def test_read_source_commit_missing_file_returns_none(tmp_path):
    skill_md = tmp_path / "SKILL.md"

    result = metadata.read_source_commit(skill_md)

    assert result is None


def test_read_source_commit_unstamped_returns_none(write_skill_md):
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  version: "0.1"']
    )

    result = metadata.read_source_commit(skill_md)

    assert result is None


def test_read_source_commit_truncates_to_seven_chars(write_skill_md):
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  source_commit: "cc9a290f1234"']
    )

    result = metadata.read_source_commit(skill_md)

    assert result == "cc9a290"


def test_stamp_under_existing_metadata_block(write_skill_md):
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  version: "0.1"']
    )

    metadata.stamp_source_commit(skill_md, "abc1234")

    assert metadata.read_source_commit(skill_md) == "abc1234"
    assert 'version: "0.1"' in skill_md.read_text(encoding="utf-8")


def test_stamp_appends_metadata_block_when_absent(write_skill_md):
    skill_md = write_skill_md(["name: soliplex-docs", "license: MIT"])

    metadata.stamp_source_commit(skill_md, "abc1234")

    text = skill_md.read_text(encoding="utf-8")
    assert "metadata:" in text
    assert metadata.read_source_commit(skill_md) == "abc1234"


def test_stamp_is_idempotent(write_skill_md):
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  source_commit: "deadbee"']
    )
    before = skill_md.read_text(encoding="utf-8")

    metadata.stamp_source_commit(skill_md, "abc1234")

    assert skill_md.read_text(encoding="utf-8") == before


def test_stamp_without_frontmatter_raises(tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Just a heading, no frontmatter\n", encoding="utf-8")

    with pytest.raises(ValueError, match="frontmatter"):
        metadata.stamp_source_commit(skill_md, "abc1234")
