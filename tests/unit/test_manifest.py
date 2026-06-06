"""Tests for :mod:`soliplex_skills.manifest`."""

from __future__ import annotations

import json

import pytest

from soliplex_skills import manifest

_PAYLOAD = {
    "tag": "docs-2026.05.29-cc9a290f",
    "source_commit": "cc9a290",
    "generated": "2026-05-29",
    "sha256": "0" * 64,
    "asset_url": "https://example.invalid/soliplex-docs-skill.tar.gz",
}


def test_from_json_parses_text():
    raw = json.dumps(_PAYLOAD)

    man = manifest.ReleaseManifest.from_json(raw)

    assert man.tag == _PAYLOAD["tag"]
    assert man.source_commit == "cc9a290"
    assert man.asset_url.endswith("soliplex-docs-skill.tar.gz")


def test_from_json_accepts_bytes_and_mapping():
    as_bytes = json.dumps(_PAYLOAD).encode("utf-8")

    from_bytes = manifest.ReleaseManifest.from_json(as_bytes)
    from_mapping = manifest.ReleaseManifest.from_json(_PAYLOAD)

    assert from_bytes == from_mapping


def test_from_json_ignores_extra_keys():
    payload = {**_PAYLOAD, "unexpected": "ignored"}

    man = manifest.ReleaseManifest.from_json(payload)

    assert man.generated == "2026-05-29"


def test_from_json_missing_field_raises():
    payload = {k: v for k, v in _PAYLOAD.items() if k != "sha256"}

    with pytest.raises(KeyError):
        manifest.ReleaseManifest.from_json(payload)


def test_to_json_round_trips_with_canonical_order():
    man = manifest.ReleaseManifest.from_json(_PAYLOAD)

    text = man.to_json()

    assert list(json.loads(text)) == [
        "tag",
        "source_commit",
        "generated",
        "sha256",
        "asset_url",
    ]
    assert manifest.ReleaseManifest.from_json(text) == man
