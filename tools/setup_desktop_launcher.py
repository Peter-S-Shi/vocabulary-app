from __future__ import annotations

import subprocess
import sys
from pathlib import Path

"""
Local, machine-specific development-launcher setup for the M16.2 desktop
preview. Creates (or updates) a Windows Desktop shortcut named
"Vocabulary App" that double-click-launches the current native PySide6
application (``python -m src.ui_desktop``) using the current Python
environment -- no manual PowerShell/terminal interaction required
afterward.

This is a development convenience tool, not M20 packaging:
- it does not build an installer or a standalone executable;
- it does not choose or freeze a Nuitka/PyInstaller packaging decision;
- the generated shortcut is machine- and checkout-specific and is never
  committed to the repository (see .gitignore); moving the checkout or
  changing the Python environment requires re-running this script.

Run once per machine/checkout, and again any time the checkout path or
Python environment changes:

    python tools/setup_desktop_launcher.py

Windows-native facilities only: no new pip dependency is added solely for
shortcut creation. Shortcut creation shells out to the ``WScript.Shell``
COM object via ``powershell.exe``, both already present on any Windows
development machine capable of running this project.
"""

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ICON_PATH = PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"
SHORTCUT_FILE_NAME = "Vocabulary App.lnk"
LAUNCH_ARGUMENTS = "-m src.ui_desktop"


def select_launch_python(current: Path | None = None) -> Path:
    """Prefer the windowed ``pythonw.exe`` next to the current interpreter
    so a normal launch does not leave a console window open; fall back to
    the current interpreter (``python.exe``) if ``pythonw.exe`` is not
    present in the same environment."""
    current = current or Path(sys.executable)
    windowed = current.with_name("pythonw.exe")
    return windowed if windowed.is_file() else current


def _powershell_quote(value: Path | str) -> str:
    """Escape a value for embedding inside a single-quoted PowerShell string."""
    return str(value).replace("'", "''")


def build_powershell_script(
    shortcut_file_name: str,
    target: Path,
    arguments: str,
    working_directory: Path,
    icon_path: Path,
    description: str,
) -> str:
    # Resolve the real per-user Desktop folder through .NET's known-folder
    # API rather than assuming "$HOME\\Desktop": that assumption breaks
    # whenever Desktop is redirected (e.g. by OneDrive Known Folder Move,
    # a common default on many Windows setups).
    return f"""
$ErrorActionPreference = 'Stop'
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop '{_powershell_quote(shortcut_file_name)}'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = '{_powershell_quote(target)}'
$shortcut.Arguments = '{_powershell_quote(arguments)}'
$shortcut.WorkingDirectory = '{_powershell_quote(working_directory)}'
$shortcut.IconLocation = '{_powershell_quote(icon_path)}'
$shortcut.Description = '{_powershell_quote(description)}'
$shortcut.Save()
Write-Output $shortcutPath
"""


def create_shortcut(shortcut_file_name: str, target: Path, working_directory: Path, icon_path: Path) -> Path:
    script = build_powershell_script(
        shortcut_file_name=shortcut_file_name,
        target=target,
        arguments=LAUNCH_ARGUMENTS,
        working_directory=working_directory,
        icon_path=icon_path,
        description="Vocabulary App desktop preview (M16.2 vertical slice)",
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Shortcut creation failed "
            f"(exit {result.returncode}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return Path(result.stdout.strip())


def main() -> int:
    if sys.platform != "win32":
        print("tools/setup_desktop_launcher.py only supports Windows.")
        return 1

    if not ICON_PATH.is_file():
        print(
            f"Expected application icon not found at {ICON_PATH}.\n"
            "Run `python tools/generate_app_icon.py` first."
        )
        return 1

    launch_python = select_launch_python()

    try:
        shortcut_path = create_shortcut(SHORTCUT_FILE_NAME, launch_python, PROJECT_ROOT, ICON_PATH)
    except RuntimeError as error:
        print(str(error))
        return 1

    print(f"Created/updated desktop shortcut: {shortcut_path}")
    print(f"Launch target: {launch_python} {LAUNCH_ARGUMENTS}")
    print(f"Working directory: {PROJECT_ROOT}")
    if launch_python.name.lower() != "pythonw.exe":
        print(
            "Note: pythonw.exe was not found next to the current Python "
            "interpreter; the shortcut uses python.exe, and a console "
            "window may briefly appear on launch."
        )
    print(
        "This shortcut is machine/checkout-specific and is not tracked by "
        "git. Re-run this script if the checkout path or Python "
        "environment changes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
