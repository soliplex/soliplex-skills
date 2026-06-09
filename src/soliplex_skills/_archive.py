"""Download, verify, extract, and install skill archives (internal).

These are the low-level filesystem/archive primitives that the public
:mod:`soliplex_skills.versions` and :mod:`soliplex_skills.install` modules
share: checksumming, download-and-extract, finding the skill root, installing
over an existing copy, and a temporary-directory context manager.

This module is private (underscore-prefixed): it is not part of the public API
and may change without notice.
"""

from __future__ import annotations

import contextlib
import hashlib
import pathlib
import shutil
import tarfile
import tempfile
from collections import abc

from soliplex_skills import releases

#: Path parts never worth downloading/comparing.
IGNORE_PARTS = frozenset({"__pycache__"})

_CHUNK = 65536


class ChecksumMismatch(ValueError):
    """A downloaded asset did not match its recorded sha256."""

    def __init__(self, expected: str, actual: str):
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"checksum mismatch: expected {expected}, got {actual}"
        )


class NoSkillFound(ValueError):
    """An extracted archive contained no ``SKILL.md``."""

    def __init__(self) -> None:
        super().__init__("no SKILL.md found in the extracted archive")


def sha256(path: pathlib.Path) -> str:
    """Return the hex sha256 digest of the file at *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


@contextlib.contextmanager
def temp_dest() -> abc.Iterator[pathlib.Path]:
    """Yield a fresh temporary directory as a ``Path`` (removed on exit)."""
    with tempfile.TemporaryDirectory() as tmp:
        yield pathlib.Path(tmp)


def download_and_extract(
    url: str, dest: pathlib.Path, *, expected_sha256: str | None = None
) -> pathlib.Path:
    """Download the tarball at *url* into *dest* and unpack it.

    When *expected_sha256* is given the download is verified before
    extraction (:class:`ChecksumMismatch` on a mismatch). Returns the
    directory the archive was extracted into; the skill itself lives in a
    single ``*/`` subdirectory beneath it (see :func:`find_skill_root`).
    """
    tarball = dest / "asset.tar.gz"
    tarball.write_bytes(releases.fetch(url, accept="application/octet-stream"))

    if expected_sha256:
        actual = sha256(tarball)
        if actual != expected_sha256:
            raise ChecksumMismatch(expected_sha256, actual)

    extract_dir = dest / "extract"
    extract_dir.mkdir()
    with tarfile.open(tarball) as archive:
        archive.extractall(extract_dir, filter="data")
    return extract_dir


def find_skill_root(extract_dir: pathlib.Path) -> pathlib.Path:
    """Return the directory containing ``SKILL.md`` under *extract_dir*."""
    matches = list(extract_dir.glob("*/SKILL.md"))
    if not matches:
        raise NoSkillFound
    return matches[0].parent


def install_over(src: pathlib.Path, dst: pathlib.Path) -> None:
    """Replace *dst*'s skill files with those from *src*, in place.

    Each top-level entry of the freshly extracted skill root (``SKILL.md``,
    ``references/``, ``scripts/``, ``assets/``) overwrites its counterpart
    under *dst*. Directories are removed first so files deleted upstream do
    not linger.
    """
    for item in sorted(src.iterdir()):
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
