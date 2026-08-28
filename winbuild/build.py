from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

"""
Repeatable build orchestration for the Windows Release Candidate (M20
Release Contract § 2.5, § 8.2 "exact source SHA -> exact build command
-> PyInstaller onedir output -> Inno Setup installer -> installer
filename -> SHA-256").

    python winbuild/build.py

Ties every artifact this produces back to the exact git commit it was
built from, and refuses to silently produce a misleadingly-labeled
build: a dirty working tree is recorded honestly in the manifest
(``source_dirty: true``), never hidden.

Two stages, run in order:
  1. PyInstaller --onedir  (always runs; this repo's frozen decision)
  2. Inno Setup compile    (runs only if ``iscc.exe`` is discoverable;
     reported as skipped, not a hard failure, so this script stays
     useful for iterating on the PyInstaller stage alone before Inno
     Setup is installed on a given machine)

Writes ``dist/build_manifest.json`` recording what was actually built,
for the RC Engineering Exit Candidate report to quote verbatim rather
than re-deriving by hand.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGING_DIR = PROJECT_ROOT / "winbuild"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
SPEC_PATH = PACKAGING_DIR / "vocabulary_app.spec"
VERSION_INFO_PATH = PACKAGING_DIR / "version_info.txt"
INNO_SCRIPT_PATH = PACKAGING_DIR / "inno_setup.iss"


class BuildError(RuntimeError):
    """A controlled, reported build-step failure."""


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(command)}")
    return subprocess.run(command, cwd=str(cwd or PROJECT_ROOT), check=False)


def get_source_sha() -> tuple[str, bool]:
    """Returns ``(head_sha, is_dirty)``. Raises ``BuildError`` if this
    is not a git checkout at all -- an untracked build has no
    verifiable provenance, which the Release Contract requires."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=PROJECT_ROOT, check=True,
            capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as error:
        raise BuildError(f"Could not determine the source git SHA: {error}") from error
    return sha, bool(status.strip())


def get_app_version() -> str:
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.app_config import APP_VERSION

    return APP_VERSION


def _parse_version_quad(version_str: str) -> tuple[int, int, int, int]:
    clean = version_str.split("-")[0].split("+")[0]
    parts = [int(p) for p in clean.split(".") if p.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    return (parts[0], parts[1], parts[2], parts[3])


def verify_version_info_matches(app_version: str) -> None:
    """winbuild/version_info.txt's version fields are hand-maintained
    (PyInstaller version-resource files are not valid Python the app itself
    can import) -- fail loudly rather than ship an installer whose
    embedded Windows file-properties versions have silently drifted from
    ``src.app_config.APP_VERSION``.

    Validates all active Windows executable/version-resource fields:
      - prodvers=(major, minor, patch, 0)
      - filevers=(major, minor, patch, 0)
      - StringStruct(u'FileVersion', u'major.minor.patch.0')
      - StringStruct(u'ProductVersion', u'<app_version>')
    """
    text = VERSION_INFO_PATH.read_text(encoding="utf-8")
    quad = _parse_version_quad(app_version)
    quad_str = ".".join(str(x) for x in quad)

    expected_checks = [
        (f"prodvers={quad}", "prodvers"),
        (f"filevers={quad}", "filevers"),
        (f"StringStruct(u'FileVersion', u'{quad_str}')", "FileVersion"),
        (f"StringStruct(u'ProductVersion', u'{app_version}')", "ProductVersion"),
    ]
    for pattern, field_name in expected_checks:
        if pattern not in text:
            raise BuildError(
                f"{VERSION_INFO_PATH} {field_name} does not match "
                f"src.app_config.APP_VERSION ({app_version}). Expected pattern: {pattern}"
            )


def run_pyinstaller() -> Path:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    completed = _run([sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_PATH)])
    if completed.returncode != 0:
        raise BuildError(f"PyInstaller failed (exit {completed.returncode}).")
    app_dir = DIST_DIR / "Vocabulary App"
    exe_path = app_dir / "Vocabulary App.exe"
    if not exe_path.is_file():
        raise BuildError(f"PyInstaller reported success but {exe_path} does not exist.")
    return app_dir


def find_inno_compiler() -> Path | None:
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        # Inno Setup's own installer defaults to a per-user install
        # here when run without elevation -- the common case on a dev
        # machine, and consistent with this project's own per-user-only
        # decision for its installer.
        candidates.append(Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    from shutil import which

    found = which("iscc") or which("ISCC")
    return Path(found) if found else None


def run_inno_setup(app_version: str, *, require_installer: bool = False) -> Path | None:
    if not INNO_SCRIPT_PATH.is_file():
        if require_installer:
            raise BuildError(f"Inno Setup script missing: {INNO_SCRIPT_PATH}")
        print(f"Skipping Inno Setup: {INNO_SCRIPT_PATH} does not exist yet.")
        return None
    compiler = find_inno_compiler()
    if compiler is None:
        if require_installer:
            raise BuildError(
                "Inno Setup compiler (ISCC.exe) not found on this machine, but an installer was required."
            )
        print("Skipping Inno Setup: ISCC.exe not found on this machine.")
        return None
    completed = _run([
        str(compiler), f"/DAppVersion={app_version}", str(INNO_SCRIPT_PATH),
    ])
    if completed.returncode != 0:
        raise BuildError(f"Inno Setup compile failed (exit {completed.returncode}).")
    output_dir = PROJECT_ROOT / "dist" / "installer"
    installers = sorted(output_dir.glob("*.exe")) if output_dir.is_dir() else []
    if not installers:
        raise BuildError(f"Inno Setup reported success but no installer found under {output_dir}.")
    installer = installers[-1]
    expected_name = f"VocabularyApp-Setup-{app_version}.exe"
    if installer.name != expected_name:
        raise BuildError(
            f"Inno Setup produced installer with unexpected filename: {installer.name} (expected {expected_name})."
        )
    return installer


# § 9 code signing. Never a hard-coded provider/tool/credential: the
# operator supplies the exact signing invocation for whichever trusted
# signing provider they set up (e.g. an AzureSignTool or signtool.exe
# command) via this environment variable, with a literal ``{file}``
# placeholder this script substitutes. Nothing signing-related is ever
# read from or written to a file in this repository.
SIGN_COMMAND_ENV = "VOCAB_APP_SIGN_COMMAND"


def sign_file(path: Path) -> bool:
    """Runs the operator-configured signing command against ``path``.
    Returns whether signing actually ran (``False`` -- not an error --
    when unconfigured, so this build script stays fully usable before a
    signing provider is set up; see § 9.2 "autonomous work before human
    involvement"). Raises ``BuildError`` if a configured command fails."""
    template = os.environ.get(SIGN_COMMAND_ENV, "").strip()
    if not template:
        print(f"Not signing {path.name}: {SIGN_COMMAND_ENV} is not set.")
        return False
    command = [part.format(file=str(path)) for part in shlex.split(template, posix=False)]
    completed = _run(command)
    if completed.returncode != 0:
        raise BuildError(f"Signing failed for {path} (exit {completed.returncode}).")
    print(f"Signed: {path}")
    return True


def verify_signature(path: Path) -> dict:
    """Independent, signing-tool-agnostic Authenticode verification via
    PowerShell's ``Get-AuthenticodeSignature`` -- real evidence the file
    carries a valid signature, not just that the signing command
    happened to exit 0 (§ 9.4 "verify the actual final installer
    carries a valid Authenticode signature")."""
    script = (
        f"$sig = Get-AuthenticodeSignature -LiteralPath '{path}'; "
        "Write-Output ($sig.Status.ToString() + '|' + "
        "$(if ($sig.SignerCertificate) { $sig.SignerCertificate.Subject } else { '' }))"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True, text=True, check=False,
    )
    status, _, subject = completed.stdout.strip().partition("|")
    return {"status": status or "Unknown", "subject": subject}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dir_size_bytes(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-inno", action="store_true", help="Build the PyInstaller onedir output only.",
    )
    parser.add_argument(
        "--require-installer", action="store_true", help="Require Inno Setup installer to be built; fail if missing.",
    )
    parser.add_argument(
        "--require-clean", action="store_true", help="Fail if the git working tree is dirty.",
    )
    args = parser.parse_args()

    source_sha, source_dirty = get_source_sha()
    if args.require_clean and source_dirty:
        raise BuildError("Working tree is dirty but --require-clean was specified.")

    app_version = get_app_version()
    verify_version_info_matches(app_version)

    print(f"Source SHA: {source_sha}{' (dirty working tree)' if source_dirty else ''}")
    print(f"App version: {app_version}")

    app_dir = run_pyinstaller()
    app_dir_size = dir_size_bytes(app_dir)
    print(f"PyInstaller onedir output: {app_dir} ({app_dir_size / (1024 * 1024):.1f} MiB)")

    # Sign the payload .exe before Inno Setup packages it, so the
    # installer wraps an already-signed executable; the installer .exe
    # itself is signed separately below, after it's built -- both
    # signed independently, the standard practice for wrapped installers.
    exe_path = app_dir / "Vocabulary App.exe"
    exe_signed = sign_file(exe_path)
    exe_signature = verify_signature(exe_path) if exe_signed else None

    installer_path = None if args.skip_inno else run_inno_setup(
        app_version, require_installer=args.require_installer,
    )
    if args.require_installer and not installer_path:
        raise BuildError("An installer was required (--require-installer) but was not produced.")

    installer_signed = sign_file(installer_path) if installer_path else False
    installer_signature = verify_signature(installer_path) if installer_signed else None
    installer_sha256 = sha256_file(installer_path) if installer_path else None

    manifest = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sha": source_sha,
        "source_dirty": source_dirty,
        "app_version": app_version,
        "onedir_path": str(app_dir),
        "onedir_size_bytes": app_dir_size,
        "onedir_exe_signed": exe_signed,
        "onedir_exe_signature": exe_signature,
        "installer_path": str(installer_path) if installer_path else None,
        "installer_sha256": installer_sha256,
        "installer_signed": installer_signed,
        "installer_signature": installer_signature,
    }
    manifest_path = DIST_DIR / "build_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Build manifest: {manifest_path}")

    # Generate SHA256SUMS.txt
    checksums: list[str] = []
    if installer_path and Path(installer_path).is_file():
        checksums.append(f"{installer_sha256}  installer/{Path(installer_path).name}")
    manifest_sha = sha256_file(manifest_path)
    checksums.append(f"{manifest_sha}  {manifest_path.name}")
    sums_path = DIST_DIR / "SHA256SUMS.txt"
    sums_path.write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(f"Checksums: {sums_path}")

    if installer_path:
        print(f"Installer: {installer_path}")
        print(f"Installer SHA-256: {installer_sha256}")
        print(f"Installer signed: {installer_signed}" + (f" ({installer_signature})" if installer_signature else ""))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as error:
        print(f"BUILD FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
