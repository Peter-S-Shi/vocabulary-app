from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.app_config import APP_VERSION
from winbuild.build import (
    SIGN_COMMAND_ENV,
    BuildError,
    VERSION_INFO_PATH,
    dir_size_bytes,
    find_inno_compiler,
    get_app_version,
    sha256_file,
    sign_file,
    verify_signature,
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
        self.assertEqual(APP_VERSION, "1.1.0")
        verify_version_info_matches(APP_VERSION)

    def test_mismatched_version_raises(self) -> None:
        with self.assertRaises(BuildError):
            verify_version_info_matches("9.9.9-does-not-exist")

    def test_partial_field_drifts_each_raise_build_error(self) -> None:
        valid_text = VERSION_INFO_PATH.read_text(encoding="utf-8")
        corrupted_cases = [
            ("ProductVersion drift", valid_text.replace(f"ProductVersion', u'{APP_VERSION}'", "ProductVersion', u'0.9.0'")),
            ("FileVersion string drift", valid_text.replace("FileVersion', u'1.1.0.0'", "FileVersion', u'1.0.0.0'")),
            ("filevers tuple drift", valid_text.replace("filevers=(1, 1, 0, 0)", "filevers=(1, 0, 0, 0)")),
            ("prodvers tuple drift", valid_text.replace("prodvers=(1, 1, 0, 0)", "prodvers=(1, 0, 0, 0)")),
        ]
        for name, bad_content in corrupted_cases:
            with self.subTest(drift_case=name):
                with patch("pathlib.Path.read_text", return_value=bad_content):
                    with self.assertRaises(BuildError) as ctx:
                        verify_version_info_matches(APP_VERSION)
                    self.assertIn("does not match", str(ctx.exception))

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


class SigningHookTests(unittest.TestCase):
    """§ 9.2 "proving the provisional artifact reaches the exact
    signing stage": these mock the configured command's own execution
    (no real signing tool needed to test the *wiring*) -- the wiring
    itself was additionally proven for real, twice: first against a
    throwaway self-signed test certificate (deleted afterward), then
    for real against the actual v1.0 Portfolio RC signing
    configuration -- a self-signed Authenticode developer certificate,
    Subject `CN=Peter Shi`, kept (not deleted) since the operator's
    Fourth Revision amendment to docs/packaging/M20_RELEASE_CONTRACT.md
    replaces the earlier "must be publicly trusted" requirement for
    this release. Both runs: sign_file() correctly invoked the
    configured PowerShell signing command, and verify_signature()
    correctly read back the resulting signature's subject and status
    (`UnknownError`/untrusted-root -- the correct, expected result for
    a self-signed certificate, not a defect)."""

    def setUp(self) -> None:
        self._original = os.environ.get(SIGN_COMMAND_ENV)

    def tearDown(self) -> None:
        if self._original is None:
            os.environ.pop(SIGN_COMMAND_ENV, None)
        else:
            os.environ[SIGN_COMMAND_ENV] = self._original

    def test_unconfigured_is_a_no_op_not_an_error(self) -> None:
        os.environ.pop(SIGN_COMMAND_ENV, None)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Vocabulary App.exe"
            target.write_bytes(b"")
            self.assertFalse(sign_file(target))

    def test_configured_command_substitutes_file_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Vocabulary App.exe"
            target.write_bytes(b"")
            os.environ[SIGN_COMMAND_ENV] = 'python -c "pass" {file}'
            with patch("winbuild.build.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                result = sign_file(target)
            self.assertTrue(result)
            called_command = mock_run.call_args[0][0]
            self.assertIn(str(target), called_command)

    def test_configured_command_failure_raises_build_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Vocabulary App.exe"
            target.write_bytes(b"")
            os.environ[SIGN_COMMAND_ENV] = 'python -c "pass" {file}'
            with patch("winbuild.build.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1
                with self.assertRaises(BuildError):
                    sign_file(target)

    def test_verify_signature_parses_status_and_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Vocabulary App.exe"
            target.write_bytes(b"")
            with patch("winbuild.build.subprocess.run") as mock_run:
                mock_run.return_value.stdout = "Valid|CN=Example Publisher\n"
                result = verify_signature(target)
            self.assertEqual(result, {"status": "Valid", "subject": "CN=Example Publisher"})


class InnoCompilerDiscoveryTests(unittest.TestCase):
    def test_finds_program_files_install_location(self) -> None:
        prog_path = Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")
        with patch.object(Path, "is_file", autospec=True, side_effect=lambda p: str(p) == str(prog_path)):
            found = find_inno_compiler()
        self.assertEqual(found, prog_path)

    def test_finds_per_user_install_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            local_app_data = Path(tmp)
            iscc_dir = local_app_data / "Programs" / "Inno Setup 6"
            iscc_dir.mkdir(parents=True)
            iscc_path = iscc_dir / "ISCC.exe"
            iscc_path.write_bytes(b"")

            def mock_is_file(p: Path) -> bool:
                return str(p) == str(iscc_path)

            with patch.dict("os.environ", {"LOCALAPPDATA": str(local_app_data)}), \
                    patch.object(Path, "is_file", autospec=True, side_effect=mock_is_file):
                found = find_inno_compiler()
            self.assertEqual(found, iscc_path)

    def test_returns_none_when_not_found_anywhere(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, \
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}), \
                patch.object(Path, "is_file", return_value=False), \
                patch("shutil.which", return_value=None):
            self.assertIsNone(find_inno_compiler())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
