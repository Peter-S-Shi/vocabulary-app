from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

LOCK_FILE_NAME = ".app_data.lock"


class DataLockError(RuntimeError):
    """Raised when acquiring an application data quiescence lock fails."""


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel32 = ctypes.windll.kernel32

    # In Win64 / Win32, ULONG_PTR is pointer-sized (c_size_t or c_void_p)
    ULONG_PTR = ctypes.c_size_t

    class OVERLAPPED(ctypes.Structure):
        _fields_ = [
            ("Internal", ULONG_PTR),
            ("InternalHigh", ULONG_PTR),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    # Explicit function prototypes for WinAPI
    _LockFileEx = kernel32.LockFileEx
    _LockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(OVERLAPPED),
    ]
    _LockFileEx.restype = wintypes.BOOL

    _UnlockFileEx = kernel32.UnlockFileEx
    _UnlockFileEx.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(OVERLAPPED),
    ]
    _UnlockFileEx.restype = wintypes.BOOL

    LOCKFILE_FAIL_IMMEDIATELY = 0x00000001
    LOCKFILE_EXCLUSIVE_LOCK = 0x00000002


class DataLockHandle:
    """Manages an active native lock on a data root with explicit lifetime."""

    def __init__(self, root: Path, exclusive: bool = False) -> None:
        self.root = Path(root).resolve()
        self.exclusive = exclusive
        self._file = None
        self._ov = None
        self._os_handle = None
        self._locked = False

    def acquire(self) -> None:
        if self._locked:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        lock_file = self.root / LOCK_FILE_NAME
        self._file = open(lock_file, "a+b")

        if sys.platform == "win32":
            self._os_handle = msvcrt.get_osfhandle(self._file.fileno())
            flags = LOCKFILE_FAIL_IMMEDIATELY
            if self.exclusive:
                flags |= LOCKFILE_EXCLUSIVE_LOCK

            self._ov = OVERLAPPED()
            success = _LockFileEx(
                wintypes.HANDLE(self._os_handle),
                wintypes.DWORD(flags),
                0,
                1,
                0,
                ctypes.byref(self._ov),
            )
            if not success:
                self._cleanup()
                mode = "exclusive migration" if self.exclusive else "active application"
                raise DataLockError(
                    f"Could not acquire {mode} lock on '{self.root}'. "
                    "Another Vocabulary App process or migration is actively using this data folder."
                )
        else:
            import fcntl

            flags = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
            flags |= fcntl.LOCK_NB
            try:
                fcntl.flock(self._file.fileno(), flags)
            except OSError as error:
                self._cleanup()
                mode = "exclusive migration" if self.exclusive else "active application"
                raise DataLockError(
                    f"Could not acquire {mode} lock on '{self.root}'. "
                    "Another Vocabulary App process or migration is actively using this data folder."
                ) from error

        self._locked = True

    def release(self) -> None:
        if not self._locked:
            return
        self._cleanup()

    def _cleanup(self) -> None:
        if self._file is not None:
            if sys.platform == "win32" and self._locked and self._os_handle is not None and self._ov is not None:
                try:
                    _UnlockFileEx(
                        wintypes.HANDLE(self._os_handle),
                        0,
                        1,
                        0,
                        ctypes.byref(self._ov),
                    )
                except OSError:
                    pass
            elif sys.platform != "win32" and self._locked:
                try:
                    import fcntl

                    fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass

            try:
                self._file.close()
            except OSError:
                pass

        self._file = None
        self._ov = None
        self._os_handle = None
        self._locked = False

    def __enter__(self) -> DataLockHandle:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    def __del__(self) -> None:
        self.release()


@contextmanager
def acquire_data_lock(root: Path, exclusive: bool = False) -> Iterator[DataLockHandle]:
    """Acquires a cross-process data lock on the specified data root folder."""
    handle = DataLockHandle(root, exclusive=exclusive)
    handle.acquire()
    try:
        yield handle
    finally:
        handle.release()
