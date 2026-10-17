from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

LOCK_FILE_NAME = ".app_data.lock"


class DataLockError(RuntimeError):
    """Raised when acquiring an application data quiescence lock fails."""


@contextmanager
def acquire_data_lock(root: Path, exclusive: bool = False) -> Iterator[None]:
    """Acquires a cross-process data lock on the specified data root folder.

    - Shared lock (exclusive=False): Used by normal running app writers
      (get_connection, save_preferences) to permit multiple concurrent app
      instances while blocking data relocation.
    - Exclusive lock (exclusive=True): Used by data relocation to guarantee
      all data writers are fully quiesced before and during relocation.

    Non-blocking: If the lock cannot be acquired immediately, raises DataLockError.
    """
    root_resolved = Path(root).resolve()
    root_resolved.mkdir(parents=True, exist_ok=True)
    lock_file = root_resolved / LOCK_FILE_NAME
    handle = None

    try:
        handle = open(lock_file, "a+b")
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            import msvcrt

            kernel32 = ctypes.windll.kernel32
            os_handle = msvcrt.get_osfhandle(handle.fileno())

            LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
            LOCKFILE_EXCLUSIVE_LOCK = 0x00000002

            flags = LOCKFILE_FAIL_IMMEDIATELY
            if exclusive:
                flags |= LOCKFILE_EXCLUSIVE_LOCK

            class OVERLAPPED(ctypes.Structure):
                _fields_ = [
                    ("Internal", ctypes.c_ulong),
                    ("InternalHigh", ctypes.c_ulong),
                    ("Offset", wintypes.DWORD),
                    ("OffsetHigh", wintypes.DWORD),
                    ("hEvent", wintypes.HANDLE),
                ]

            ov = OVERLAPPED()
            success = kernel32.LockFileEx(
                wintypes.HANDLE(os_handle),
                wintypes.DWORD(flags),
                0,
                1,
                0,
                ctypes.byref(ov),
            )
            if not success:
                mode = "exclusive migration" if exclusive else "active application"
                raise DataLockError(
                    f"Could not acquire {mode} lock on '{root_resolved}'. "
                    "Another Vocabulary App process or migration is actively using this data folder."
                )
        else:
            import fcntl

            flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            flags |= fcntl.LOCK_NB
            try:
                fcntl.flock(handle.fileno(), flags)
            except OSError as error:
                mode = "exclusive migration" if exclusive else "active application"
                raise DataLockError(
                    f"Could not acquire {mode} lock on '{root_resolved}'. "
                    "Another Vocabulary App process or migration is actively using this data folder."
                ) from error

        yield

    finally:
        if handle is not None:
            try:
                if sys.platform == "win32":
                    import ctypes
                    from ctypes import wintypes
                    import msvcrt

                    kernel32 = ctypes.windll.kernel32
                    os_handle = msvcrt.get_osfhandle(handle.fileno())

                    class OVERLAPPED(ctypes.Structure):
                        _fields_ = [
                            ("Internal", ctypes.c_ulong),
                            ("InternalHigh", ctypes.c_ulong),
                            ("Offset", wintypes.DWORD),
                            ("OffsetHigh", wintypes.DWORD),
                            ("hEvent", wintypes.HANDLE),
                        ]

                    ov = OVERLAPPED()
                    kernel32.UnlockFileEx(
                        wintypes.HANDLE(os_handle),
                        0,
                        1,
                        0,
                        ctypes.byref(ov),
                    )
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                handle.close()
            except OSError:
                pass
