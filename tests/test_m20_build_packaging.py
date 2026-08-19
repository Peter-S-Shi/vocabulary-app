from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app_config import APP_VERSION
from winbuild.build import (
    BuildError,
    VERSION_INFO_PATH,
    dir_size_bytes,
    find_inno_compiler,
    get_app_version,
    sha256_file,
    verify_version_info_matches,
)

"""
Focused tests for the M20 build orchestration script
(winbuild/build.py -- Release Contract § 2.5, § 8.2 "exact source SHA ->
exact build command -> PyInstaller onedir output -> Inno Setup installer
-> installer filename -> SHA-256"). Covers the script's pure logic
(version-drift guard, hashing, size accounting, compiler discovery) --
not a full PyInstaller/Inno Setup build, which
winbuild/build.py itself was already run and manually verified against
a real installer produced from this checkout (installs/launches, Local
Windows Speech Provider scripts resolve, uninstall preserves/deletes
data correctly per the explicit opt-in).

The package is named ``winbuild``, not ``packaging`` -- deliberately,
to avoid shadowing the widely-installed PyPI ``packaging`` library
(pip/setuptools depend on it); confirmed a real collision existed
before the rename (``import packaging`` resolved to site-packages, not
this directory).
"""


class VersionInfoDriftGuardTests(unittest.TestCase):
    def test_current_app_version_matches_version_info_file(self) -> None:
        """The real, checked-in file must already agree with
        src.app_config.APP_VERSION -- this is the regression this
        function exists to catch before a release ships an installer
        with a stale embedded Windows file-properties version."""
        verify_version_info_matches(APP_VERSION)

    def test_mismatched_version_raises(self) -> None:
        with self.assertRaises(BuildError):
            verify_version_info_matches("9.9.9-does-not-exist")

    def test_get_app_version_returns_the_real_app_config_value(self) -> None:
        self.assertEqual(get_app_version(), APP_VERSION)


class HashingAndSizeTests(unittest.TestCase):
    def test_sha256_file_matches_hashlib_directly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.bin"
            payload = b"vocabulary app installer bytes" * 1000
            path.write_bytes(payload)
            expected = hashlib.sha256(payload).hexdigest()
            self.assertEqual(sha256_file(path), expected)

    def test_dir_size_bytes_sums_only_files_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.txt").write_bytes(b"1234")
            nested = root / "nested"
            nested.mkdir()
            (nested / "b.txt").write_bytes(b"12345678")
            self.assertEqual(dir_size_bytes(root), 4 + 8)


class InnoCompilerDiscoveryTests(unittest.TestCase):
    def test_finds_per_user_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_app_data = Path(tmp)
            iscc_dir = local_app_data / "Programs" / "Inno Setup 6"
            iscc_dir.mkdir(parents=True)
            iscc_path = iscc_dir / "ISCC.exe"
            iscc_path.write_bytes(b"")
            with patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}):
                found = find_inno_compiler()
            self.assertEqual(found, iscc_path)

    def test_returns_none_when_not_found_anywhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}), \
                patch("shutil.which", return_value=None):
            self.assertIsNone(find_inno_compiler())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
