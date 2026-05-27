from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

from keyboard_assistant.core.models import AppContext


class AppDetector:
    """Best-effort active app detector with a Windows implementation."""

    def current_app(self) -> AppContext:
        if not _is_windows_available():
            return AppContext()
        try:
            return _current_windows_app()
        except OSError:
            return AppContext()


def _is_windows_available() -> bool:
    return hasattr(ctypes, "windll")


def _current_windows_app() -> AppContext:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return AppContext()

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    title_buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, title_buffer, 512)

    process_name = ""
    access_query_limited_information = 0x1000
    process = kernel32.OpenProcess(access_query_limited_information, False, pid.value)
    if process:
        try:
            path_buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(path_buffer))
            query_full_process_image_name = ctypes.windll.kernel32.QueryFullProcessImageNameW
            if query_full_process_image_name(process, 0, path_buffer, ctypes.byref(size)):
                process_name = Path(path_buffer.value).name
        finally:
            kernel32.CloseHandle(process)

    return AppContext(
        app_name=process_name,
        app_identifier=process_name.lower(),
        window_title=title_buffer.value,
    )

