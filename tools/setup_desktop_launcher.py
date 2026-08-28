import ctypes
from ctypes import Structure, byref, c_ulong, c_ushort, c_void_p, c_wchar_p, wintypes
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ui_desktop.app import WINDOWS_APP_USER_MODEL_ID  # noqa: E402

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
"""

ICON_PATH = PROJECT_ROOT / "assets" / "icons" / "vocabulary_app.ico"
SHORTCUT_FILE_NAME = "Vocabulary App.lnk"
LAUNCH_ARGUMENTS = "-m src.ui_desktop"


def set_shortcut_app_user_model_id(shortcut_path: Path | str, aumid: str = WINDOWS_APP_USER_MODEL_ID) -> bool:
    """Attach the explicit System.AppUserModel.ID property to a Windows shortcut (.lnk).

    Aligning the shortcut's AppUserModelID with the running process's AUMID ensures
    that Windows Shell seamlessly associates clicked shortcuts with running windows,
    maintaining single-group taskbar pinning and preventing duplicate icons.
    """
    if sys.platform != "win32":
        return False

    try:
        class GUID(Structure):
            _fields_ = [("Data1", c_ulong), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD), ("Data4", wintypes.BYTE * 8)]

        class PROPERTYKEY(Structure):
            _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

        class PROPVARIANT(Structure):
            _fields_ = [
                ("vt", c_ushort),
                ("wReserved1", wintypes.WORD),
                ("wReserved2", wintypes.WORD),
                ("wReserved3", wintypes.WORD),
                ("pwszVal", c_wchar_p),
            ]

        CLSID_ShellLink = GUID(0x00021401, 0, 0, (wintypes.BYTE * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
        IID_IShellLinkW = GUID(0x000214F9, 0, 0, (wintypes.BYTE * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
        IID_IPersistFile = GUID(0x0000010B, 0, 0, (wintypes.BYTE * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))
        IID_IPropertyStore = GUID(0x886D8EEB, 0x8CF2, 0x4446, (wintypes.BYTE * 8)(0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))
        PKEY_AppUserModel_ID = PROPERTYKEY(
            GUID(0x9F4C2855, 0x9F79, 0x4B39, (wintypes.BYTE * 8)(0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)),
            5,
        )

        ole32 = ctypes.windll.ole32
        ole32.CoInitialize(None)

        p_sl = c_void_p()
        hr = ole32.CoCreateInstance(byref(CLSID_ShellLink), None, 1, byref(IID_IShellLinkW), byref(p_sl))
        if hr != 0 or not p_sl:
            return False

        sl_vtable = ctypes.cast(p_sl, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
        QueryInterface = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(c_void_p))(sl_vtable[0])

        p_pf = c_void_p()
        hr = QueryInterface(p_sl, byref(IID_IPersistFile), byref(p_pf))
        if hr != 0 or not p_pf:
            ctypes.WINFUNCTYPE(c_ulong, c_void_p)(sl_vtable[2])(p_sl)
            return False

        pf_vtable = ctypes.cast(p_pf, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
        Load = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, wintypes.LPCWSTR, wintypes.DWORD)(pf_vtable[5])
        Save = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, wintypes.LPCWSTR, wintypes.BOOL)(pf_vtable[6])

        # STGM_READWRITE = 2
        hr_load = Load(p_pf, str(shortcut_path), 2)
        if hr_load != 0:
            ctypes.WINFUNCTYPE(c_ulong, c_void_p)(pf_vtable[2])(p_pf)
            ctypes.WINFUNCTYPE(c_ulong, c_void_p)(sl_vtable[2])(p_sl)
            return False

        p_ps = c_void_p()
        hr = QueryInterface(p_sl, byref(IID_IPropertyStore), byref(p_ps))
        success = False
        if hr == 0 and p_ps:
            ps_vtable = ctypes.cast(p_ps, ctypes.POINTER(ctypes.POINTER(c_void_p))).contents
            SetValue = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(PROPVARIANT))(ps_vtable[6])
            Commit = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p)(ps_vtable[7])

            pv = PROPVARIANT(31, 0, 0, 0, aumid)  # VT_LPWSTR = 31
            hr_set = SetValue(p_ps, byref(PKEY_AppUserModel_ID), byref(pv))
            hr_commit = Commit(p_ps)
            if hr_set == 0 and hr_commit == 0:
                Save(p_pf, str(shortcut_path), True)
                success = True

            ctypes.WINFUNCTYPE(c_ulong, c_void_p)(ps_vtable[2])(p_ps)

        ctypes.WINFUNCTYPE(c_ulong, c_void_p)(pf_vtable[2])(p_pf)
        ctypes.WINFUNCTYPE(c_ulong, c_void_p)(sl_vtable[2])(p_sl)
        return success
    except Exception:
        return False


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
        description="Vocabulary App (v1.1)",
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
    shortcut_path = Path(result.stdout.strip())
    set_shortcut_app_user_model_id(shortcut_path, WINDOWS_APP_USER_MODEL_ID)
    return shortcut_path


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
