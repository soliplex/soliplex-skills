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
        [
            "name: soliplex-docs",
            'description: "Soliplex docs."',
            "metadata:",
            '  version: "0.1"',
        ]
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

    metadata.stamp_metadata(skill_md, source_commit="abc1234")

    assert metadata.read_source_commit(skill_md) == "abc1234"
    assert 'version: "0.1"' in skill_md.read_text(encoding="utf-8")


def test_stamp_appends_metadata_block_when_absent(write_skill_md):
    skill_md = write_skill_md(["name: soliplex-docs", "license: MIT"])

    metadata.stamp_metadata(skill_md, source_commit="abc1234")

    text = skill_md.read_text(encoding="utf-8")
    assert "metadata:" in text
    assert metadata.read_source_commit(skill_md) == "abc1234"


def test_stamp_is_idempotent(write_skill_md):
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  source_commit: "deadbee"']
    )
    before = skill_md.read_text(encoding="utf-8")

    metadata.stamp_metadata(skill_md, source_commit="abc1234")

    assert skill_md.read_text(encoding="utf-8") == before


def test_stamp_without_frontmatter_raises(tmp_path):
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Just a heading, no frontmatter\n", encoding="utf-8")

    with pytest.raises(ValueError, match="frontmatter"):
        metadata.stamp_metadata(skill_md, source_commit="abc1234")


def test_stamp_metadata_entries_are_readable(write_skill_md):
    # The added entries should be observable to a reader -- and the quoting we
    # write must parse back to the bare values -- alongside the pre-existing
    # ``source_commit``, which is left intact.
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  source_commit: "abc1234"']
    )

    metadata.stamp_metadata(skill_md, version="v1.2.3", generated="2026-06-09")

    assert metadata._read_metadata(skill_md) == {
        "source_commit": "abc1234",
        "version": "v1.2.3",
        "generated": "2026-06-09",
    }


def test_stamp_metadata_creates_metadata_block_when_absent(write_skill_md):
    # A SKILL.md with no ``metadata:`` block at all still ends up with every
    # stamped entry readable -- i.e. a parseable block was synthesized.
    skill_md = write_skill_md(["name: soliplex-docs", "license: MIT"])

    metadata.stamp_metadata(
        skill_md,
        version="v1.2.3",
        source_commit="abc1234",
        generated="2026-06-09",
    )

    assert metadata._read_metadata(skill_md) == {
        "version": "v1.2.3",
        "source_commit": "abc1234",
        "generated": "2026-06-09",
    }


def test_stamp_metadata_writes_canonical_order(write_skill_md):
    # Order is invisible to a YAML reader, but the entries are deliberately
    # laid out in STAMP_KEYS order for humans reading the file -- a formatting
    # guarantee, checked here against the raw text.
    skill_md = write_skill_md(["name: soliplex-docs", "license: MIT"])

    metadata.stamp_metadata(
        skill_md, version="v1", source_commit="abc1234", generated="2026-06-09"
    )

    text = skill_md.read_text(encoding="utf-8")
    assert (
        text.index("version:")
        < text.index("source_commit:")
        < text.index("generated:")
    )


def test_stamp_metadata_preserves_a_key_already_present(write_skill_md):
    # Stamping is per-key idempotent: a reader keeps seeing the pre-existing
    # ``version`` (not the one passed here), while a genuinely new key lands.
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  version: "0.1"']
    )

    metadata.stamp_metadata(skill_md, version="v9.9.9", generated="2026-06-09")

    metadata_table = metadata._read_metadata(skill_md)
    assert metadata_table["version"] == "0.1"
    assert metadata_table["generated"] == "2026-06-09"


def test_stamp_metadata_omits_a_key_left_unset(write_skill_md):
    # A ``None`` argument writes nothing, so a reader never sees that key.
    skill_md = write_skill_md(
        ["name: soliplex-docs", "metadata:", '  source_commit: "abc1234"']
    )

    metadata.stamp_metadata(skill_md, generated="2026-06-09")

    metadata_table = metadata._read_metadata(skill_md)
    assert "version" not in metadata_table
    assert metadata_table["generated"] == "2026-06-09"
